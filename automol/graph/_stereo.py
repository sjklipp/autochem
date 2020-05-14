""" stereo graph library
"""
import itertools
import functools
import numpy
from automol import dict_
from automol.graph._res import (resonance_dominant_atom_hybridizations as
                                _resonance_dominant_atom_hybridizations)
from automol.graph._res import (resonance_dominant_bond_orders as
                                _resonance_dominant_bond_orders)
from automol.graph._graph import atoms as _atoms
from automol.graph._graph import bonds as _bonds
from automol.graph._graph import atom_stereo_parities as _atom_stereo_parities
from automol.graph._graph import bond_stereo_parities as _bond_stereo_parities
from automol.graph._graph import (set_atom_stereo_parities as
                                  _set_atom_stereo_parities)
from automol.graph._graph import (set_bond_stereo_parities as
                                  _set_bond_stereo_parities)
from automol.graph._graph import without_bond_orders as _without_bond_orders
from automol.graph._graph import (without_stereo_parities as
                                  _without_stereo_parities)
from automol.graph._graph import frozen as _frozen
from automol.graph._graph import atom_bond_valences as _atom_bond_valences
from automol.graph._graph import atom_neighbor_keys as _atom_neighbor_keys
from automol.graph._graph import explicit as _explicit
from automol.graph._graph import implicit as _implicit
from automol.graph._graph import backbone_keys as _backbone_keys
from automol.graph._graph import (explicit_hydrogen_keys as
                                  _explicit_hydrogen_keys)
from automol.graph._graph import rings_bond_keys as _rings_bond_keys


def has_stereo(xgr):
    """ does this graph have stereo of any kind?
    """
    return bool(atom_stereo_keys(xgr) or bond_stereo_keys(xgr))


def atom_stereo_keys(sgr):
    """ keys to atom stereo-centers
    """
    atm_ste_keys = dict_.keys_by_value(_atom_stereo_parities(sgr),
                                       lambda x: x in [True, False])
    return atm_ste_keys


def bond_stereo_keys(sgr):
    """ keys to bond stereo-centers
    """
    bnd_ste_keys = dict_.keys_by_value(_bond_stereo_parities(sgr),
                                       lambda x: x in [True, False])
    return bnd_ste_keys


def stereo_priority_vector(xgr, atm_key, atm_ngb_key):
    """ generates a sortable one-to-one representation of the branch extending
    from `atm_key` through its bonded neighbor `atm_ngb_key`
    """
    bbn_keys = _backbone_keys(xgr)
    exp_hyd_keys = _explicit_hydrogen_keys(xgr)

    if atm_ngb_key not in bbn_keys:
        assert atm_ngb_key in exp_hyd_keys
        assert frozenset({atm_key, atm_ngb_key}) in _bonds(xgr)
        pri_vec = ()
    else:
        xgr = _implicit(xgr)
        atm_dct = _atoms(xgr)
        bnd_dct = _bonds(xgr)
        assert atm_key in bbn_keys
        assert frozenset({atm_key, atm_ngb_key}) in bnd_dct

        # here, switch to an implicit graph
        atm_ngb_keys_dct = _atom_neighbor_keys(xgr)

        def _priority_vector(atm1_key, atm2_key, seen_keys):
            # we keep a list of seen keys to cut off cycles, avoiding infinite
            # loops

            bnd_val = bnd_dct[frozenset({atm1_key, atm2_key})]
            atm_val = atm_dct[atm2_key]

            bnd_val = _replace_nones_with_negative_infinity(bnd_val)
            atm_val = _replace_nones_with_negative_infinity(atm_val)

            if atm2_key in seen_keys:
                ret = (bnd_val,)
            else:
                seen_keys.update({atm1_key, atm2_key})
                atm3_keys = atm_ngb_keys_dct[atm2_key] - {atm1_key}
                if atm3_keys:
                    next_vals, seen_keys = zip(*[
                        _priority_vector(atm2_key, atm3_key, seen_keys)
                        for atm3_key in atm3_keys])
                    ret = (bnd_val, atm_val) + next_vals
                else:
                    ret = (bnd_val, atm_val)

            return ret, seen_keys

        pri_vec, _ = _priority_vector(atm_key, atm_ngb_key, set())

    return pri_vec


def _replace_nones_with_negative_infinity(seq):
    return [-numpy.inf if val is None else val for val in seq]


def stereogenic_atom_keys(xgr):
    """ (unassigned) stereogenic atoms in this graph
    """
    xgr = _without_bond_orders(xgr)
    xgr = _explicit(xgr)  # for simplicity, add the explicit hydrogens back in
    atm_keys = dict_.keys_by_value(_atom_bond_valences(xgr), lambda x: x == 4)
    atm_keys -= atom_stereo_keys(xgr)

    atm_ngb_keys_dct = _atom_neighbor_keys(xgr)

    def _is_stereogenic(atm_key):
        atm_ngb_keys = list(atm_ngb_keys_dct[atm_key])
        pri_vecs = [stereo_priority_vector(xgr, atm_key, atm_ngb_key)
                    for atm_ngb_key in atm_ngb_keys]
        return not any(pv1 == pv2
                       for pv1, pv2 in itertools.combinations(pri_vecs, r=2))

    ste_gen_atm_keys = frozenset(filter(_is_stereogenic, atm_keys))
    return ste_gen_atm_keys


def stereogenic_bond_keys(xgr):
    """ (unassigned) stereogenic bonds in this graph
    """
    xgr = _without_bond_orders(xgr)
    xgr = _explicit(xgr)  # for simplicity, add the explicit hydrogens back in
    bnd_keys = dict_.keys_by_value(
        _resonance_dominant_bond_orders(xgr), lambda x: 2 in x)

    # make sure both ends are sp^2 (excludes cumulenes)
    atm_hyb_dct = _resonance_dominant_atom_hybridizations(xgr)
    sp2_atm_keys = dict_.keys_by_value(atm_hyb_dct, lambda x: x == 2)
    bnd_keys = frozenset({bnd_key for bnd_key in bnd_keys
                          if bnd_key <= sp2_atm_keys})

    bnd_keys -= bond_stereo_keys(xgr)
    bnd_keys -= functools.reduce(  # remove double bonds in small rings
        frozenset.union,
        filter(lambda x: len(x) < 8, _rings_bond_keys(xgr)), frozenset())

    atm_ngb_keys_dct = _atom_neighbor_keys(xgr)

    def _is_stereogenic(bnd_key):
        atm1_key, atm2_key = bnd_key

        def _is_symmetric_on_bond(atm_key, atm_ngb_key):
            atm_ngb_keys = list(atm_ngb_keys_dct[atm_key] - {atm_ngb_key})

            if not atm_ngb_keys:                # C=:O:
                ret = True
            elif len(atm_ngb_keys) == 1:        # C=N:-X
                ret = False
            else:
                assert len(atm_ngb_keys) == 2   # C=C(-X)-Y
                ret = (stereo_priority_vector(xgr, atm_key, atm_ngb_keys[0]) ==
                       stereo_priority_vector(xgr, atm_key, atm_ngb_keys[1]))

            return ret

        return not (_is_symmetric_on_bond(atm1_key, atm2_key) or
                    _is_symmetric_on_bond(atm2_key, atm1_key))

    ste_gen_bnd_keys = frozenset(filter(_is_stereogenic, bnd_keys))
    return ste_gen_bnd_keys


def stereomers(xgr):
    """ all stereomers, ignoring this graph's assignments
    """
    bool_vals = (False, True)

    def _expand_atom_stereo(sgr):
        atm_ste_keys = stereogenic_atom_keys(sgr)
        nste_atms = len(atm_ste_keys)
        sgrs = [_set_atom_stereo_parities(sgr, dict(zip(atm_ste_keys,
                                                        atm_ste_par_vals)))
                for atm_ste_par_vals
                in itertools.product(bool_vals, repeat=nste_atms)]
        return sgrs

    def _expand_bond_stereo(sgr):
        bnd_ste_keys = stereogenic_bond_keys(sgr)
        nste_bnds = len(bnd_ste_keys)
        sgrs = [_set_bond_stereo_parities(sgr, dict(zip(bnd_ste_keys,
                                                        bnd_ste_par_vals)))
                for bnd_ste_par_vals
                in itertools.product(bool_vals, repeat=nste_bnds)]
        return sgrs

    last_sgrs = []
    sgrs = [_without_stereo_parities(xgr)]

    while sgrs != last_sgrs:
        last_sgrs = sgrs
        sgrs = list(itertools.chain(*map(_expand_atom_stereo, sgrs)))
        sgrs = list(itertools.chain(*map(_expand_bond_stereo, sgrs)))

    return tuple(sorted(sgrs, key=_frozen))


def substereomers(xgr):
    """ all stereomers compatible with this graph's assignments
    """
    _assigned = functools.partial(
        dict_.filter_by_value, func=lambda x: x is not None)

    known_atm_ste_par_dct = _assigned(_atom_stereo_parities(xgr))
    known_bnd_ste_par_dct = _assigned(_bond_stereo_parities(xgr))

    def _is_compatible(sgr):
        atm_ste_par_dct = _assigned(_atom_stereo_parities(sgr))
        bnd_ste_par_dct = _assigned(_bond_stereo_parities(sgr))
        _compat_atm_assgns = (set(known_atm_ste_par_dct.items()) <=
                              set(atm_ste_par_dct.items()))
        _compat_bnd_assgns = (set(known_bnd_ste_par_dct.items()) <=
                              set(bnd_ste_par_dct.items()))
        return _compat_atm_assgns and _compat_bnd_assgns

    sgrs = tuple(filter(_is_compatible, stereomers(xgr)))
    return sgrs


def stereo_sorted_atom_neighbor_keys(xgr, atm_key, atm_ngb_keys):
    """ get the neighbor keys of an atom sorted by stereo priority
    """
    atm_ngb_keys = list(atm_ngb_keys)

    # explicitly create an object array because otherwise the argsort
    # interprets [()] as []
    atm_pri_vecs = numpy.empty(len(atm_ngb_keys), dtype=numpy.object_)
    atm_pri_vecs[:] = [stereo_priority_vector(xgr, atm_key, atm_ngb_key)
                       for atm_ngb_key in atm_ngb_keys]

    sort_idxs = numpy.argsort(atm_pri_vecs)
    sorted_atm_ngb_keys = tuple(map(atm_ngb_keys.__getitem__, sort_idxs))
    return sorted_atm_ngb_keys
