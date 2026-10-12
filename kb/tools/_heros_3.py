# kb/tools/_heros_3.py — fiches héros (couche jugement), lot 3/3 (p-z).
# Données pures ; l'écriture des .md est faite par seed_heros.py.

HEROS = {
"probius": """**Rôle** : spécialiste de zone — pylônes et canons (Photon Cannon), rifts de zone, Disruption Pulse.
**Menaces** : dive direct (il est le plus fragile du jeu) ; les chasseurs qui détruisent ses pylônes (Junkrat, Hanzo) ; les compo mobiles.
**À exploiter** : les objectifs fixes (son setup verrouille une zone entière) ; les choke points ; les maps à point unique (Volskaya, Braxis).
**Pièges** : sans son setup il ne fait rien — le poser AVANT l'objectif, pas pendant ; Warp est son seul escape.
**Synergies** : tanks qui verrouillent la zone (Johanna, Blaze, Mei), setups de regroupement, Abathur (hat de protection).
""",
"qhira": """**Rôle** : assassin mêlée de survie — grappin, invulnérabilité pendant son spin, Carnage (ult de zone).
**Menaces** : CC chain pendant son spin ; blinds (ses autos) ; les compo qui la focus dès qu'elle entre.
**À exploiter** : les teamfights longues (sa survie dépend du dégât qu'elle inflige) ; les backlines qu'elle peut harceler ; les zones groupées.
**Pièges** : sans dégâts elle ne survit pas (son trait = heal sur dégâts) ; son grappin est aussi son escape — ne pas tout engager.
**Synergies** : Uther (DS), Auriel (ses dégâts = heal), setups de regroupement (Johanna, E.T.C.).
""",
"ragnaros": """**Rôle** : bruiser de défense — trait de fort (Molten Core = défendre une structure), sulfuras smash, Blast Wave.
**Menaces** : kiting (il est mêlé) ; les compo qui n'attaquent pas les structures (son trait perd sa valeur) ; % damage.
**À exploiter** : la défense de forts et keeps (Molten Core = défenseur de zone) ; les teamfights sur objectif (son AoE) ; les maps à push constant.
**Pièges** : Molten Core est défensif — ne pas l'attendre pour engager ; son engage est court, jouer en contre-engage.
**Synergies** : setups de zone (Johanna, Garrosh), heals de zone (Stukov, Deckard), compo qui défend (Sgt. Hammer).
""",
"raynor": """**Rôle** : assassin ranged de fiabilité — autos simples et fortes, inspire (buff d'équipe), Hyperion / Raider.
**Menaces** : dive rapide (Genji, Zeratul, Tracer) ; blinds (ses autos sont tout) ; les compo qui le focus en premier.
**À exploiter** : les tanks (il tape fort et loin) ; les parties simples où la fiabilité gagne ; inspire = buff de toute l'équipe.
**Pièges** : pas de dash — son Positioning est la seule défense ; Hyperion pousse une lane, pas un teamfight.
**Synergies** : Abathur (hat), Lt. Morales (Stim Drone), Auriel (dégâts constants = Hope), Uther (DS).
""",
"rehgar": """**Rôle** : support polyvalent — chain heal, totem de slow, Bloodlust / Ancestral Healing.
**Menaces** : dive ciblé (il est mêlé pour taper) ; anti-heal (Ana) ; les compo qui le forcent à dépenser Ancestral tôt.
**À exploiter** : les compo mêlée (chain heal = heal de groupe) ; Ancestral Healing = sauvegarde de carry (le garder pour ça) ; son totem de slow en engage.
**Pièges** : Ancestral est réactif et se rate sur les cibles qui bougent — la précision est tout ; Ghost Wolf n'est pas un escape en teamfight.
**Synergies** : hypercarries (Illidan, Valla, Greymane — Ancestral), compo mêlée (Sonya, Thrall, Kerrigan), Bloodlust + autos (Valla, Zul'jin).
""",
"rexxar": """**Rôle** : bruiser à deux corps — Rexxar + Misha (l'ours qui tank/stun), zone de contrôle.
**Menaces** : les chasseurs de Misha (la tuer = Rexxar nu) ; dive direct sur Rexxar (il est squishy derrière) ; % damage sur Misha.
**À exploiter** : la tenue de point (Misha cap pendant que Rexxar reste en sécurité) ; le stun de Misha = setup d'équipe ; les maps à objectif fixe.
**Pièges** : micro de deux corps permanente ; Misha qui meurt = plus de tank pendant 15 s ; ne pas envoyer Misha sans possibilité de rappel.
**Synergies** : bursts sur le stun de Misha (Li-Ming, Kael'thas), compo de point (Volskaya, Braxis, Shrines).
""",
"samuro": """**Rôle** : assassin de chaos — clones (illusions), invisibilité momentanée, Image Transmission.
**Menaces** : la vision et les AoE (ses clones se voient dans les zones de dégâts) ; les compo qui le kiten ; blinds.
**À exploiter** : le split-push (ses clones clear les waves) ; les duels 1v1 (il est très fort en duel) ; le chaos des teamfights (les adversaires tapent le mauvais).
**Pièges** : ses clones nourrissent de l'XP s'ils meurent — les rappeler ; son dégât en teamfight groupée est limité, c'est un duelliste.
**Synergies** : globals et macro (Abathur, Dehaka), setups qui profitent du chaos, Illidan (double split).
""",
"sgthammer": """**Rôle** : spécialiste de siège — mode Siege (portée énorme), Mines, Blunt Force Gun.
**Menaces** : dive rapide (elle est immobile en mode Siege) ; les longues portées (Chromie, Hanzo, Li-Ming) ; les compo qui la forcent à bouger.
**À exploiter** : les zones d'objectif (sa portée les rend impossibles à tenir pour l'adversaire) ; la défense de keeps ; les murs et choke points.
**Pièges** : mode Siege = cible fixe — ne l'activer qu'avec une équipe autour ; Booster est son escape, le garder pour le dive.
**Synergies** : tanks qui verrouillent la zone (Johanna, Garrosh, Blaze), Abathur (hat de protection), Medivh (portail d'évacuation).
""",
"sonya": """**Rôle** : bruiser de duel — spin (Whirlwind), lifesteal, Leap (ult d'engage).
**Menaces** : kiting (elle doit être collée) ; blinds (ses autos = son heal) ; % damage (Tychus, Malthael).
**À exploiter** : les duels de lane et de camp (excellente en solo) ; les teamfights groupées (Whirlwind) ; les cibles qui restent collées.
**Pièges** : Fury = sa ressource — ne pas engager sans fury ; Whirlwind la rend vulnérable aux stuns (interrompu = rien).
**Synergies** : heals qui la maintiennent (Lt. Morales, Rehgar), setups de regroupement (Whirlwind dans un Mosh), Uther (DS pendant son spin).
""",
"stitches": """**Rôle** : tank de pick — Hook (accroche mythique), Gorge (avaler une cible), zone de slow (Putrid Bile).
**Menaces** : kiting (il est lent et sans vrai engage) ; % damage (Tychus, Malthael) ; les compo qui restent derrière leurs minions.
**À exploiter** : les hooks sur cible clé (un hook = un kill) ; les choke points ; les mages immobiles (Chromie, Kael'thas, Ana).
**Pièges** : un hook raté = 15 s où il ne fait rien ; Gorge sur la mauvaise cible (avaler un tank vivant = le sauver).
**Synergies** : burst sur le hooké (Li-Ming, Kael'thas, Jaina, Kel'Thuzad), Anduin (Leap qui rattrape ses gaffes), Uther (DS).
""",
"stukov": """**Rôle** : support de zone — heals en zone (Lurking Arm = silence de zone), Massive Shove (ult de displacement).
**Menaces** : dive ciblé (il est lent) ; anti-heal (Ana) ; les compo mobiles qui sortent de ses zones.
**À exploiter** : les zones d'objectif (Lurging Arm = silence de zone qui verrouille) ; les compo groupées (ses heals de zone) ; Massive Shove = pick ou disengage.
**Pièges** : ses heals ont un délai (les spores) — les poser avant le dégât ; Lurking Arm est un channel, interrompre = rien.
**Synergies** : tanks de zone (Johanna, Blaze, Mei), setups de regroupement, compo qui tient le point (Volskaya, Shrines).
""",
"sylvanas": """**Rôle** : spécialiste de push — silence (Wailing Arrow), trait de disable de structure, Mind Control.
**Menaces** : dive rapide (elle est squishy) ; les compo qui la focus (son trait est précieux en push) ; kiting.
**À exploiter** : les pushes d'objectif (son trait neutralise les structures pendant que l'équipe pousse) ; Wailing Arrow = silence d'équipe en engage ; les maps à objectif qui pousse (Shrines, Braxis).
**Pièges** : son trait est un cooldown d'équipe — ne pas le gaspiller sur des minions ; Mind Control la place au premier plan.
**Synergies** : pushes avec objectif (Ragnaros, Azmodan), setups (Johanna pull + silence), Uther (DS).
""",
"tassadar": """**Rôle** : assassin/support hybride — shields, Archon (ult de dégâts), Plasma Shield, Force Wall.
**Menaces** : dive (il est squishy en forme normale) ; les compo qui cassent ses shields rapidement ; kiting.
**À exploiter** : les hypercarries (ses shields = vie gratuite) ; Force Wall = mur de contrôle (surtout en combo avec Garrosh) ; Archon en fin de teamfight.
**Pièges** : Force Wall bloque les alliés aussi — le placer pour l'adversaire ; ses shields ont un CD, ne pas les gaspiller sur le poke.
**Synergies** : Illidan, Tracer, Zul'jin (shields = hypercarry), Garrosh (throw + wall), Abathur (double shield).
""",
"thebutcher": """**Rôle** : assassin de snowball — charge (Ruthless Onslaught), lifesteal qui monte avec les stacks de trait (Fresh Meat).
**Menaces** : blinds (ses autos sont tout — Johanna, Cassia, Li Li, Artanis) ; kiting ; les compo qui le focus dès qu'il charge.
**À exploiter** : les squishies isolés (charge = kill) ; les parties où il peut stacker (tuer des héros = plus fort) ; les compo sans blind.
**Pièges** : sans stacks il est faible — il DOIT tuer des héros ; sa charge est tout ou rien, l'annuler à mi-chemin = mort.
**Synergies** : Abathur (hat = Butcher immortel), Uther (DS pendant sa charge), Rehgar (Ancestral), Auriel (dégâts = heal).
""",
"thrall": """**Rôle** : bruiser de poke mêlé — Chain Lightning (poke), Sundering (ult de displacement), lifesteal de trait.
**Menaces** : kiting (il est mêlé sans dash) ; % damage (Tychus, Malthael) ; blinds.
**À exploiter** : les duels de lane (son sustain) ; Sundering = split d'équipe adverse (séparer le tank de son heal) ; les zones de choke.
**Pièges** : Sundering mal placé = sauver l'adversaire (comme un mauvais Gust) ; son poke est bon mais son engage est faible.
**Synergies** : bursts sur le split de Sundering (Li-Ming, Kael'thas), setups (Johanna), heals de sustain (Rehgar).
""",
"tracer": """**Rôle** : assassin de harcèlement — blink, Recall (annule ses erreurs), Pulse Bomb.
**Menaces** : point-and-click stun (Uther, Muradin, Brightwing Polymorph) ; blinds (ses autos) ; les compo qui la one-shot en CC chain.
**À exploiter** : les backlines sans stun (Ana, Li-Ming, Chromie) ; le harcèlement permanent (elle ne s'arrête jamais) ; finir les kills bas.
**Pièges** : Recall est sa vie — ne jamais l'engager sans lui ; Pulse Bomb se rate sur les cibles mobiles, le poser après un stun allié.
**Synergies** : Abathur (hat = Tracer folle), Uther (DS), Medivh (portail), setups de stun (le sien est faible).
""",
"tychus": """**Rôle** : assassin anti-tank — % damage sur autos (trait), minigun, Odin (ult de zone), Grenade.
**Menaces** : kiting (il est court en portée) ; blinds (ses autos = son % damage) ; dive direct (Genji, Zeratul).
**À exploiter** : les tanks (THE counter de tank) ; les cibles à gros PV (Cho'gall, Deathwing, Diablo) ; Odin pour les zones d'objectif.
**Pièges** : sa portée est courte — le positionnement est tout ; Odin le rend gros et visible, pas invulnérable.
**Synergies** : setups de slow (Arthas, Jaina) pour le laisser coller, Uther (DS), Auriel (dégâts = Hope).
""",
"tyrael": """**Rôle** : tank de support d'équipe — shields d'alliés, Sanctification (invulnérabilité de zone), Judgment (engage).
**Menaces** : % damage (Tychus, Malthael) ; kiting (il est mêlé sans accroche) ; les compo qui kiten son équipe.
**À exploiter** : Sanctification = invulnérabilité de teamfight (annule Mosh, Pyroblast, tout) ; Judgment sur un mage ; le support de dive allié.
**Pièges** : il ne « tank » pas au sens classique — sans son équipe qui suit, il ne fait rien ; Sanctification se joue en réaction, pas en engage.
**Synergies** : dives alliés (Illidan, Genji, Greymane — il les suit), compo qui gagne en invulnérabilité (Sonya, Kael'thas).
""",
"tyrande": """**Rôle** : support/assassin hybride — mark (Hunter's Mark = + dégâts), heal, stun (Lunar Flare), Shadowstalk (invisibilité d'équipe).
**Menaces** : dive ciblé (elle est squishy) ; les compo qui la focus (son heal est faible sans trait) ; kiting.
**À exploiter** : le mark = focus d'équipe sur une cible ; Shadowstalk = engage surprise ou disengage ; son stun de zone.
**Pièges** : en support unique ses heals sont limités — mieux en double support ; Lunar Flare se rate, la viser sur les cibles CC-ées.
**Synergies** : bursts qui suivent son mark (Greymane, Li-Ming, Hanzo), vision combinée (Hanzo, Medivh), Nova/Abathur (mark + snipe).
""",
"uther": """**Rôle** : support de sauvegarde — stun de point-and-click, Divine Shield (invulnérabilité), armure d'équipe (trait de mort).
**Menaces** : kiting (il est lent et mêlé) ; anti-heal (Ana) ; les compo qui le forcent à dépenser DS tôt.
**À exploiter** : Divine Shield sur la carry qui engage (Illidan, Genji, Butcher, Greymane) ; son stun = counter de tout dive ; ses heals de burst.
**Pièges** : il est lent à dépenser sa mana (ses heals sont chers) ; DS est le meilleur ult du jeu — ne jamais le gaspiller par panique.
**Synergies** : hypercarries all-in (Illidan, Genji, Butcher, Greymane, Zul'jin), E.T.C. (DS + Mosh), compo mêlée (ses heals sont de zone à la mort).
""",
"valeera": """**Rôle** : assassin de pick — invisibilité, silence (Garrote), Cheap Shot (stun), Vanish.
**Menaces** : la vision (Tyrande, Medivh, Hanzo, Lunara) ; les compo groupées (elle exige une cible isolée) ; les tanks qui la déclenchent.
**À exploiter** : les backlines isolés (Ana, Li-Ming, Chromie, Kael'thas) ; les rotations ; le silence sur les healers pendant l'engage.
**Pièges** : elle ne fait rien en teamfight ouverte — jouer les picks et les flanks ; révéler sa position = perdre sa menace.
**Synergies** : setups (son silence = combo d'équipe), Abathur (hat), burst qui suit son stun (Li-Ming).
""",
"valla": """**Rôle** : hypercarry ranged — autos empilées (trait), vault, strafe / Rain of Vengeance.
**Menaces** : dive rapide (Genji, Zeratul, Tracer, Valeera) ; blinds (ses autos) ; toute compo qui la focus en premier.
**À exploiter** : les tanks et les teamfights longues (son trait monte sans limite) ; les compo qui la protègent ; les zones de choke (Rain).
**Pièges** : elle est le premier focus de la carte — le positionnement et l'escape (Vault) sont tout ; perdre ses stacks de trait = perdre ses dégâts.
**Synergies** : Abathur (hat), Lt. Morales (Stim), Uther (DS), Auriel (Hope infinie), Tassadar (shields), Rehgar (Bloodlust).
""",
"varian": """**Rôle** : multiclass selon l'ult — Colossus Smash (burst), Twin Blades (sustain), Taunt (tank de pick).
**Menaces** : kiting (il est mêlé) ; blinds (Twin Blades) ; les compo qui savent quelle variante il joue et le kiten en conséquence.
**À exploiter** : la variante adaptée à la compo (Taunt = pick garanti, Smash = delete de squishy) ; Warbringer = engage de stun long.
**Pièges** : il choisit sa voie à 10 — sauter sur le mauvais choix gâche la partie ; Taunt sans follow-up = juste un stun.
**Synergies** : Abathur (hat = Varian monstrueux), bursts sur son Taunt (Li-Ming, Kael'thas), Uther (DS).
""",
"whitemane": """**Rôle** : support de burst de soin — Desperation (trait d'énergie), Scarlet Aegis (ult d'armure), Inquisition.
**Menaces** : anti-heal (Ana) ; dive ciblé ; les compo qui la forcent à dépenser sa Desperation tôt.
**À exploiter** : les teamfights où l'équipe prend des pics de dégâts (ses soins sont en burst) ; les tanks qui absorbent tout ; les duels prolongés.
**Pièges** : sa ressource se gagne en tapant — elle doit être en position de taper pour soigner ; ses soins sont chers, la gestion de Despression est tout.
**Synergies** : tanks qui prennent du dégât visible (Johanna, Garrosh, Diablo), compo mêlée (elle est proche pour taper).
""",
"xul": """**Rôle** : spécialiste de wave — clear de wave monstrueux (Bone Armor, Spectral Scythe), skeletal mages (ult de slow).
**Menaces** : kiting (il est lent) ; les compo qui le kiten sans minions ; % damage.
**À exploiter** : le push de wave (il clear 2 lanes à lui tout seul) ; les zones de choke (son slow de trait) ; les maps à 3 lanes.
**Pièges** : il est faible en duel ouvert — jouer la macro, pas les teamfights ; son clear nourrit des stacks adverses (Nazeebo, Alarak ?) — attention aux match-ups.
**Synergies** : macro (Abathur, Dehaka, Lost Vikings), setups de regroupement, compo qui pousse pendant qu'il split.
""",
"yrel": """**Rôle** : tank bruiser de tenue — jump, knockback, heals de zone (Ardent Defender), très dure à tuer.
**Menaces** : kiting (elle est lente à se mettre en place) ; % damage (Tychus, Malthael) ; les compo qui la ignorent.
**À exploiter** : la tenue de point (elle ne meurt jamais) ; le peel de son backline (knockback) ; les zones d'objectif.
**Pièges** : ses capacités se chargent (canal) — les placer avant l'engage, pas pendant ; Ardent Defender est son outil de survie ultime, le garder pour le vrai burst.
**Synergies** : compo de point (Volskaya, Braxis, Shrines), hypercarries protégées (Valla, Zul'jin), heals de zone (Stukov, Deckard).
""",
"zagara": """**Rôle** : spécialiste de push et de vision — Nydus (réseau de tunnels), broods, Maw (ult d'isolement de zone).
**Menaces** : dive rapide (elle est squishy) ; les compo qui clear ses broods ; les chasseurs de Nydus.
**À exploiter** : la vision permanente (creep = vision de la map) ; le split multi-lane (Nydus) ; les zones de choke (Maw = isolation).
**Pièges** : son creep se clear (les adversaires attentifs le font) ; Maw isole des ennemis mais PAS leurs dégâts — le timing est tout.
**Synergies** : macro (Abathur, Dehaka), setups pour Maw (Johanna, E.T.C.), compo qui pousse (Sgt. Hammer, Azmodan).
""",
"zarya": """**Rôle** : tank/support hybride — shields d'alliés (Particle Grenade), energy qui monte, Graviton Surge (ult de pull de zone).
**Menaces** : kiting (elle est moyennement mobile) ; les compo qui attendent la fin de ses shields ; % damage.
**À exploiter** : les compo qui tapent les alliés (ses shields = énergie = dégâts) ; Graviton Surge = combo de toute l'équipe ; les teamfights longues.
**Pièges** : ses shields sont courts — les poser sur le bon allié au bon moment ; sans énergie elle ne fait pas de dégâts.
**Synergies** : toute l'AoE pendant Graviton (Kael'thas, Jaina, Gul'dan, Mephisto), dives qu'elle protège (Illidan, Genji), Uther (DS).
""",
"zeratul": """**Rôle** : assassin de pick — invisibilité, Vorpal Blade (chase), Void Prison (ult d'isolement).
**Menaces** : la vision (Tyrande, Medivh, Hanzo, Lunara) ; les compo groupées (il exige une cible isolée) ; point-and-click stun.
**À exploiter** : les backlines isolés (Ana, Li-Ming, Chromie) ; Void Prison = setup de combo (ou sauver un allié) ; les rotations de flanc.
**Pièges** : Void Prison est le double tranchant ultime — un mauvais VP sauve l'adversaire ; il ne clear rien, jouer les picks.
**Synergies** : bursts après VP (Kael'thas, Jaina, Li-Ming), Abathur (hat), Medivh (portail de sortie).
""",
"zuljin": """**Rôle** : hypercarry ranged — autos qui montent avec ses PV perdus (trait), Taz'dingo (invulnérabilité), axe de slow.
**Menaces** : blinds (ses autos sont tout) ; kiting ; les compo qui le burst avant qu'il active Taz'dingo.
**À exploiter** : les teamfights longues (son trait = dégâts qui montent) ; Taz'dingo = 4 s de DPS gratuit ; les tanks qu'il mord.
**Pièges** : jouer à demi-PV est sa force MAIS un stun = mort ; Taz'dingo se counter par le kite (attendre la fin).
**Synergies** : Rehgar (Bloodlust + Ancestral), Uther (DS), Auriel (ses dégâts = Hope), Abathur (hat), Lt. Morales (Stim).
""",
}
