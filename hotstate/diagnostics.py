"""Closed vocabulary for exported diagnostics. Never export exception repr/args.

Categories describe guards, not a retrospective diagnosis of a match. Unknown
codes remain unknown; adding a code requires a reviewed source change.
"""
CODES = {
    'menu': {'aucune_simulation_active'},
    'budget': {'budget_pipeline_depasse', 'fenetre_pipeline_globale_depassee'},
    'build': {'profil_natif_invalide', 'build_natif_non_pris_en_charge',
              'signature_native_invalide', 'profil_contexte_natif_invalide',
              'signature_contexte_native_invalide', 'profil_partie_native_invalide',
              'signature_partie_native_invalide', 'profil_chrono_non_pris_en_charge',
              'signature_chrono_invalide', 'profil_positions_non_pris_en_charge',
              'signature_positions_invalide', 'profil_identite_positions_absent',
              'signature_identite_positions_invalide', 'profil_visibilite_non_pris_en_charge',
              'signature_visibilite_invalide', 'profil_objectif_non_pris_en_charge',
              'signature_objectif_invalide', 'profil_dragon_invalide',
              'signature_dragon_invalide', 'code_vm_dragon_invalide',
              'script_vm_objectif_invalide'},
    'context_identity': {
        'pipeline_live_contexte_natif_requis', 'contexte_requis', 'coeur_pipeline_absent',
        'contexte_natif_absent', 'contexte_natif_invalide_ou_ambigu',
        'contexte_natif_partie_changee', 'effectif_contexte_natif_invalide',
        'option_contexte_natif_invalide', 'chaine_contexte_native_invalide',
        'cache_partie_native_invalide', 'contexte_natif_capture_non_atomique',
        'perspective_native_incoherente', 'identite_locale_native_incoherente',
        'identifiant_joueur_natif_incoherent', 'identifiant_heros_natif_invalide',
        'heros_natif_inconnu', 'encodage_joueurs_non_pris_en_charge',
        'proprietaire_ou_generation_unite_incoherent', 'reference_unite_native_invalide',
        'contexte_natif_absent', 'contexte_natif_incomplet',
        'partie_native_absente', 'partie_native_incoherente',
        'racine_partie_native_invalide', 'partie_application_non_active',
        'perspective_observateur_ou_replay', 'identite_locale_native_absente',
        'identite_ou_equipe_native_invalide', 'equipes_natives_non_5v5',
        'identite_positions_absente', 'identite_positions_absente_ou_ambigue',
        'identite_positions_native_incoherente', 'contexte_positions_modifie',
        'perspective_dragon_incoherente', 'perspective_objectif_incoherente',
        'contexte_live_dragon_requis',
    },
    'incoherence': {
        'lecture_native_dechiree', 'contexte_natif_dechire',
        'memoire_native_incomplete', 'observation_native_non_synchrone',
        'horloge_native_invalide', 'liste_composants_native_invalide',
        'nombre_composants_natif_invalide', 'niveau_natif_invalide',
        'composant_experience_absent', 'scan_pipeline_natif_interdit',
        'lecture_positions_dechiree', 'lecture_visibilite_dechiree',
        'lecture_dragon_dechiree', 'lecture_champ_bataille_dechiree',
        'talent_torn', 'cooldown_torn',
        'lecture_chrono_dechiree', 'lecture_objectif_dechiree',
        'objective_packet_rejected',
        # Literal guards from the existing Dragon/Volskaya objective producers.
        # Preserve the reason, not a claimed diagnosis or new map permission.
        'beacon_dragon_duplique', 'borne_vm_dragon_invalide', 'borne_vm_objectif_invalide',
        'bornes_objectif_incoherentes', 'compte_composants_objectif_invalide',
        'compte_durees_objectif_invalide', 'descripteur_comportement_objectif_invalide',
        'duree_objectif_hors_bornes', 'duree_objectif_infinie',
        'equipe_pilote_dragon_invalide', 'equipe_protecteur_objectif_incoherente',
        'etat_capture_dragon_invalide', 'etat_point_objectif_invalide',
        'expiration_timer_objectif_incoherente', 'fin_liste_durees_objectif_invalide',
        'flag_duree_objectif_invalide', 'generation_type_timer_objectif_invalide',
        'index_catalogue_objectif_invalide', 'index_vm_dragon_invalide',
        'index_vm_objectif_invalide', 'liaison_sanctuaire_dragon_invalide',
        'liste_composants_objectif_invalide', 'liste_durees_objectif_invalide',
        'marqueur_canalisation_dragon_invalide', 'nom_comportement_objectif_invalide',
        'nom_vm_dragon_invalide', 'nom_vm_objectif_invalide',
        'nombre_sanctuaires_dragon_invalide', 'objet_timer_objectif_invalide',
        'phase_dragon_invalide', 'pilote_dragon_invalide', 'pilote_protecteur_objectif_invalide',
        'point_et_protecteur_objectif_incoherents', 'pointeur_objectif_invalide',
        'points_actifs_objectif_ambigus', 'proprietaire_protecteur_objectif_invalide',
        'proprietaire_sanctuaire_dragon_invalide', 'proprietaire_unite_dragon_invalide',
        'proprietaires_capture_dragon_incoherents', 'racine_vm_dragon_invalide',
        'racine_vm_objectif_invalide', 'reference_protecteur_objectif_invalide',
        'reference_timer_objectif_invalide', 'registre_timer_objectif_invalide',
        'statue_sanctuaires_dragon_incoherents', 'timer_objectif_non_initialise',
        'type_unite_dragon_invalide', 'vie_protecteur_objectif_invalide',
    },
    'freshness': {
        'etat_perime', 'contexte_natif_perime', 'perspective_native_perimee_ou_modifiee',
        'fenetre_ou_contexte_visibilite_invalide', 'fenetre_dragon_invalide',
        'talent_stale_or_context_changed', 'cooldown_window_or_context_changed',
        'fenetre_positions_trop_large', 'fenetre_chrono_trop_large',
        'fenetre_objectif_invalide',
    },
    'optional_unqualified': {
        'champ_bataille_non_valide_en_recette',
        'recette_positions_absente', 'recette_positions_joueur_absente',
        'carte_positions_non_prise_en_charge', 'recette_objectifs_absente',
        'carte_ou_capture_objectif_non_prise_en_charge',
        'carte_ou_capture_champ_bataille_non_prise_en_charge',
        'recette_visibilite_joueur_absente', 'recette_dragon_absente',
        'recette_objectif_absente', 'recette_champ_bataille_absente',
        'recette_champ_bataille_dragon_absente', 'recette_cooldowns_absente',
        'carte_dragon_requise', 'carte_volskaya_requise',
        'carte_ou_capture_dragon_non_prise_en_charge',
        'carte_ou_capture_champ_bataille_dragon_non_prise_en_charge',
        'talent_recipe_scope_unqualified', 'talent_no_qualified_player',
    },
}


def refusal(value):
    if type(value) is str:
        for category, codes in CODES.items():
            if value in codes:
                return {'code': value, 'category': category}
    return {'code': 'unknown_refusal', 'category': 'unknown'}


def exception_refusal(exc):
    # Do not call __str__ on arbitrary errors or interpolate their payload.
    from .native import NativeUnavailable
    return refusal(exc.args[0] if type(exc) is NativeUnavailable and len(exc.args) == 1 else None)


def coherence_detail(value):
    """Closed core guard location, NOT bytes, addresses or a causal diagnosis."""
    if type(value) is not dict:
        return None
    phase, field, width = value.get('phase'), value.get('field'), value.get('width')
    if (type(phase) is not str or phase not in ('initial_overlap', 'final_equality')
            or type(field) is not str or field not in (
                'build', 'identity', 'clock_roots', 'clock_tick', 'core_state',
                'generation', 'roster', 'life', 'level', 'respawn', 'vitals', 'unclassified')
            or type(width) is not int or not 1 <= width <= 65536):
        return None
    detail = {'phase': phase, 'field': field, 'width': width}
    transition = value.get('clock_transition')
    if (field == 'clock_tick' and width == 4 and type(transition) is str
            and transition in ('forward_bounded', 'forward_over_window', 'backward', 'out_of_range')):
        detail['clock_transition'] = transition
    return detail
