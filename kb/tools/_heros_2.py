# kb/tools/_heros_2.py — fiches héros (couche jugement), lot 2/3 (h-o).
# Données pures ; l'écriture des .md est faite par seed_heros.py.

HEROS = {
"hanzo": """**Rôle** : assassin de poke — flèches longue portée, Sonic Arrow (vision), Scatter Arrow (burst de zones).
**Menaces** : dive rapide (Genji, Zeratul, Tracer, Valeera) ; les murs qui cassent ses angles de Scatter ; les compo qui le forcent au corps-à-corps.
**À exploiter** : les zones serrées (Scatter = burst monstrueux) ; les objectifs (vision + poke gratuit) ; les tanks qui lui servent de mire (Dragonstrike en zone).
**Pièges** : sa portée est sa vie — s'approcher pour un auto est souvent une erreur ; Sonic Arrow perdu = l'équipe joue sans vision à l'objectif.
**Synergies** : setups de stun (Muradin, E.T.C., Diablo), vision combinée (Tyrande, Medivh), tanks qui immobilisent pour ses flèches.
""",
"hogger": """**Rôle** : bruiser de chaos — Hogg Wild (ricochets de dégâts), displacement, très dur à attraper.
**Menaces** : % damage (Tychus, Malthael) ; les zones ouvertes sans mur (ses ricochets y sont faibles) ; CC chain bref mais répété.
**À exploiter** : les zones fermées (Hogg Wild = dégâts de zone énormes) ; le backline (il entre et ressort) ; les objectifs en zone.
**Pièges** : jouer en zone ouverte = dégâts divisés ; ses sorties demandent des murs — connaître les angles de chaque map.
**Synergies** : setups de regroupement (Johanna pull, E.T.C. Mosh), heals de zone (Stukov, Deckard).
""",
"illidan": """**Rôle** : assassin de dive et de chase — lifesteal, esquive (Evasion), The Hunt (ult de lock).
**Menaces** : blinds (Johanna, Cassia, Li Li, Artanis — ses autos sont TOUT) ; Arthas (slow) ; Uther (stun) ; toute compo qui garde son peel pour lui.
**À exploiter** : les compo sans blind ni hard CC ; les backlines isolées (Ana, Li-Ming, Chromie) ; les maps à camps (il les prend sans coût).
**Pièges** : sans support il fond (c'est un hypercarry, pas un solo) ; The Hunt sur une cible protégée = suicide à distance.
**Synergies** : Abathur (hat = Illidan immortel), Uther (Divine Shield), Tassadar (shields), Auriel (dégâts = heal), Brightwing (Polymorph sur ses menaces).
""",
"imperius": """**Rôle** : tank bruiser — engage de lance (Valorous Brand = dégâts empilables), Solarion's Wrath.
**Menaces** : kiting (ses combos exigent d'être collé) ; % damage (Tychus, Malthael) ; les compo qui dispersent ses brands.
**À exploiter** : les duels de front (son burst de brands) ; les cibles qui restent collées à lui ; les zones d'objectif.
**Pièges** : ses dégâts demandent de rester sur la même cible — le switch permanent l'annule ; son engage est court, pas un vrai Muradin jump.
**Synergies** : stuns de setup (Muradin, Uther), heals qui le maintiennent en mêlée (Lt. Morales, Ana).
""",
"jaina": """**Rôle** : mage de burst — slow permanent (Frost), Blizzard, Ring of Frost (ult de zone).
**Menaces** : dive rapide (Genji, Zeratul, Tracer) ; les compo qui absorbent son burst (shields, Divine Shield) ; vision qui révèle ses positions.
**À exploiter** : les compo groupées (Blizzard + slow = zone de mort) ; les tanks lents (elles leur font mal) ; les choke points.
**Pièges** : elle est squishy et sans dash — le positionnement est 80 % du jeu ; Ice Block est son seul vrai outil de survie, le garder pour le dive.
**Synergies** : setups de regroupement (Johanna pull, E.T.C. Mosh, Garrosh throw), Uther (DS), Medivh (portail de position).
""",
"johanna": """**Rôle** : tank de contrôle — pull (Condemn), blind (Shield Glare), Blessed Shield (stun en ligne).
**Menaces** : % damage (Tychus, Malthael) ; kiting (elle est lente) ; les compo qui la ignorent (elle tape peu).
**À exploiter** : les compo auto-attacks (blind) ; les regroupements (Condemn = setup de toute l'équipe) ; le clear de wave (excellent).
**Pièges** : Iron Skin est sa vie — le garder pour le CC adverse, pas pour le poke ; Condemn sans follow-up ne fait que déplacer l'ennemi.
**Synergies** : toute l'AoE (Kael'thas, Gul'dan, Jaina, Mephisto — Condemn est le setup universel), Auriel (ses dégâts en masse).
""",
"junkrat": """**Rôle** : assassin de zone et de disruption — mines (displacement), RIP-Tire, poke de grenade.
**Menaces** : dive rapide qui passe ses zones (Genji, Zeratul, Tracer) ; les heals qui absorbent son poke ; vision (ses mines se voient).
**À exploiter** : les zones de choke (mines + grenades) ; le displacement (mine = envoyer un ennemi dans votre équipe) ; le clear de wave.
**Pièges** : RIP-Tire est lent et audible — le lancer en chaos de teamfight, pas en ouverture ; ses dégâts à distance sont prévisibles, les angles comptent.
**Synergies** : setups de stun (Muradin, E.T.C.), Garrosh (throw + mine), zones fixes (Shrines, Volskaya).
""",
"kaelthas": """**Rôle** : mage de burst de zone — Flamestrike, Gravity Lapse (stun), Pyroblast / Phoenix.
**Menaces** : dive rapide (Genji, Zeratul, Tracer, Valeera) ; les shields qui absorbent Pyroblast (Divine Shield, Medivh) ; kiting.
**À exploiter** : les compo groupées (Flamestrike empilé = wipe) ; les zones de choke ; les tanks qui lui servent de relais (Living Bomb spread).
**Pièges** : il est le premier dive target de la carte — position TOUJOURS derrière ; Pyroblast se counter en 10 façons, le réserver aux cibles sans protection.
**Synergies** : Johanna (Condemn = Flamestrike garanti), E.T.C. (Mosh), Medivh (portail + protection), Anduin (Leap de sauvetage).
""",
"kelthuzad": """**Rôle** : mage de combo — chaînes (Chains of Kel'Thuzad), burst glacé, Shadow Fissure.
**Menaces** : dive rapide (il est le mage le plus fragile) ; les compo mobiles (ses chaînes se ratent) ; Cleanse.
**À exploiter** : les cibles immobiles ou CC-ées (chaîne = stun = burst = kill) ; les zones de choke ; les tanks qui lui servent d'ancre.
**Pièges** : il doit stacker son trait (dégâts de complétion) — jouer agressif tôt pour finir ses stacks ; sans stun setup, ses chaînes sont un pari.
**Synergies** : setups de stun (Muradin, E.T.C., Diablo, Garrosh), Medivh (protection pendant ses combos), Uther (DS).
""",
"kerrigan": """**Rôle** : assassin de combo mêlée — Ravage (jump), Primal Grasp + Impale (stun en cône), Ultralisk.
**Menaces** : kiting (elle est collée à sa cible) ; blinds (ses autos) ; peel massif (Uther, Brightwing) ; les compo qui ne la laissent pas finir son combo.
**À exploiter** : les backlines groupées (son combo de zone) ; les picks dans les buissons ; les squishies qui s'approchent.
**Pièges** : combo raté = elle est en mêlée sans rien ; Ravage est aussi son escape — ne pas le gaspiller pour farm.
**Synergies** : Abathur (hat), Uther (DS), Auriel (dégâts = heal), setups de regroupement (Johanna).
""",
"kharazim": """**Rôle** : support mêlée — dégâts OU heals selon le trait choisi, Divine Palm / Seven-Sided Strike.
**Menaces** : CC chain en mêlée (il doit être collé pour soigner) ; blinds (ses autos = ses heals) ; kiting.
**À exploiter** : les compo qui jouent collées (ses heals de zone) ; Seven-Sided Strike sur les tanks (dégâts = % de PV max).
**Pièges** : choisir le trait dégâts quand l'équipe n'a pas d'autre heal = erreur de draft ; Divine Palm est réactif — le poser avant le burst, pas après.
**Synergies** : dives alliés (Illidan, Genji, Greymane — il les suit), compo mêlée (Sonya, Thrall).
""",
"leoric": """**Rôle** : bruiser anti-tank — % damage (Spectral Leech), drain de vie, Entomb (ult de mur).
**Menaces** : kiting (il est lent) ; les compo qui le kiten sans tank à taper ; anti-heal qui casse son drain.
**À exploiter** : les tanks (son drain = % de PV) ; Entomb sur une cible sans dash (kill garanti avec burst) ; la mort « gratuite » (il revient vite en fantôme).
**Pièges** : sans tank adverse il perd beaucoup de sa valeur ; Entomb se dash out — vérifier les escapes avant de l'engager.
**Synergies** : burst sur l'entombé (Li-Ming, Kael'thas, Jaina), setups de mur (Garrosh throw dans l'Entomb).
""",
"lili": """**Rôle** : support anti-auto-attacks — Blind (Blinding Winds), heals automatiques (Cloud Serpent), Jug of 1,000 Cups.
**Menaces** : burst pur (ses heals sont faibles sur une cible unique) ; anti-heal (Ana) ; kiting de sa position.
**À exploiter** : les compo auto-attacks (Illidan, Butcher, Valla, Zul'jin aveuglés) ; les longs combats (ses heals sont gratuits et continus).
**Pièges** : ses heals visent la cible la plus blessée automatiquement — elle ne « choisit » pas ; Fast Feet exige de bouger, s'arrêter = mourir.
**Synergies** : compo qui tankent longtemps (Johanna, Arthas, Blaze), Auriel en double support.
""",
"liming": """**Rôle** : assassin de reset — burst longue portée (Disintegrate / Arcane Orb), resets sur kill, Teleport.
**Menaces** : dive rapide (Genji, Zeratul, Tracer, Valeera — elle est squishy) ; les tanks qui absorbent son burst ; vision qui la localise.
**À exploiter** : les kills en cascade (son reset gagne les teamfights) ; les zones de choke (Orb) ; les cibles déjà blessées.
**Pièges** : ses dégâts sont télégraphiés (Orb se dodge) — taper les cibles CC-ées ; Teleport est son seul escape, jamais pour s'approcher.
**Synergies** : setups de regroupement (Johanna, E.T.C., Garrosh), Medivh (portail + protection), Uther (DS), Abathur (hat).
""",
"lostvikings": """**Rôle** : macro pur — 3 corps pour soak les 3 lanes, Longboat Raid / Play Again.
**Menaces** : les chasseurs de Viking (Tracer, Genji, Zeratul, Nova — un Viking tué = XP offerte) ; les compo qui pushent fort en early.
**À exploiter** : les maps à 3 lanes (Tomb, Cursed Hollow, Warhead) : 3 lanes soakées = avantage d'XP permanent ; les objectifs où l'équipe se regroupe.
**Pièges** : chaque mort de Viking nourrit l'adversaire — les replier dès qu'un chasseur est repéré ; la micro de 3 corps demande de l'attention continue.
**Synergies** : toute l'équipe qui joue 4v5 forts (Abathur, globals), les objectifs qui forcent l'adversaire à se regrouper.
""",
"ltmorales": """**Rôle** : support mono-cible — heal continu (trait), Stim Drone (ult de hypercarry), Medivac (transport).
**Menaces** : dive ciblé (elle n'a aucun escape) ; anti-heal (Ana) ; les compo qui ignorent le tank et viennent la chercher.
**À exploiter** : les tanks qui absorbent tout (son heal est infini sur une cible) ; Stim Drone sur une hypercarry (Valla, Raynor, Zul'jin) ; Medivac = rotations de groupe instantanées.
**Pièges** : elle ne heal qu'une cible à la fois — si l'équipe prend des dégâts de zone, elle ne suit pas ; se coller au tank qui la protège.
**Synergies** : hypercarries (Valla, Raynor, Zul'jin, Greymane), tanks murs (Johanna, Garrosh, Diablo), Medivac + globals (Dehaka).
""",
"lucio": """**Rôle** : support de mobilité — heals de zone passifs, speed boost, Sound Barrier (ult de shield d'équipe).
**Menaces** : burst pur (ses heals sont lents et continus) ; anti-heal (Ana) ; silence (Brightwing, Uther) qui casse son aura.
**À exploiter** : les compo mobiles et agressives (speed boost = engage permanent) ; les échappées (speed = disengage gratuit) ; les zones d'objectif.
**Pièges** : son heal est faible en burst — Sound Barrier doit couvrir le pic de dégâts adverse, pas la fin ; Crossfade se gère en continu, un mauvais mode tue.
**Synergies** : dives alliés (Illidan, Genji, Greymane — le speed), compo de rotation (Johanna, Blaze), E.T.C. (speed + Mosh).
""",
"lunara": """**Rôle** : assassin de poke — poison (dégrad), vision (Wisp), slow constant.
**Menaces** : dive rapide (elle est squishy et sans dash) ; les heals de burst qui annulent son poison ; blinds (ses autos).
**À exploiter** : les compo sustain (son poison est un anti-sustain naturel) ; kiting des tanks lents ; vision permanente (Wisp).
**Pièges** : son dégât est lent — ne pas viser des kills instantanés ; Wisp mal placé = la team joue sans vision à l'objectif.
**Synergies** : slows cumulés (Arthas, Jaina), setups de stun qui laissent son poison finir, Auriel (ses dégâts constants = Hope).
""",
"maiev": """**Rôle** : assassin de zone — pull (Umbral Bind), Warden's Cage (ult de zone), reset de trait.
**Menaces** : kiting (elle doit être collée) ; les compo qui ne se groupent pas (son pull exige plusieurs cibles) ; % damage.
**À exploiter** : les compo groupées (Cage = wipe) ; les backlines collées (pull + burst) ; les zones de choke.
**Pièges** : Warden's Cage sans follow-up ne fait que les enfermer avec vous ; son trait demande de taper plusieurs héros pour reset.
**Synergies** : burst de zone (Kael'thas, Jaina, Gul'dan pendant le Cage), setups (Johanna, E.T.C.), Abathur (hat).
""",
"malfurion": """**Rôle** : support de zone et de CC — heals en HoT (Regrowth), Roots, Twilight Dream (ult de silence de zone).
**Menaces** : dive ciblé (pas d'escape) ; anti-heal qui annule ses HoT (Ana) ; les compo qui one-shot (ses heals sont en continu, pas en burst).
**À exploiter** : les longs combats (ses HoT gagnent à l'usure) ; Root = setup de toute l'équipe ; Twilight Dream en counter-engage.
**Pièges** : ses HoT prennent du temps — les poser AVANT le dégât ; Innervate est une ressource à gérer, pas un bouton automatique.
**Synergies** : tanks qui prennent du dégât prévisible (Johanna, Arthas), setups de Root (E.T.C., Garrosh), compo qui durent (Auriel double support).
""",
"malganis": """**Rôle** : tank de disruption — sleep (Night Rush), drain de vie, Carrion Swarm (ult de phase).
**Menaces** : kiting (il est lent) ; % damage (Tychus, Malthael) ; les compo qui jouent dispersées (son sleep est de zone).
**À exploiter** : les compo groupées (sleep de zone = teamfight choisie) ; les dives qu'il neutralise ; les longs combats (drain).
**Pièges** : Night Rush se voit venir — le lancer depuis un angle ; Carrion Swarm le rend invulnérable mais il ne fait rien pendant, timing de survie.
**Synergies** : burst après sleep (Li-Ming, Kael'thas), setups de zone (Johanna), heals qui prolongent son drain.
""",
"malthael": """**Rôle** : assassin anti-tank — % damage (Last Rites = exécution), phase (Wraith Walk), zone de dégâts.
**Menaces** : kiting (il est mêlé) ; les compo sans tank (son % damage perd sa cible) ; burst sur lui pendant Wraith Walk en CD.
**À exploiter** : les tanks et bruisers (Tychus en version fantôme) ; les zones de fight prolongées (son trait) ; Last Rites sur une cible à % de PV.
**Pièges** : sans tank adverse il est faible ; Last Rites se heal/shield (Divine Shield, Medivh) — vérifier les protections.
**Synergies** : slows (Arthas, Jaina) pour le laisser coller, Uther (DS), setups de regroupement.
""",
"medivh": """**Rôle** : support de protection — Force of Will (invulnérabilité), portails, Poly Bomb / Ley Line Seal.
**Menaces** : les compo qui punissent ses portails (ils sont visibles) ; silence (Brightwing, Uther) ; les chasseurs qui le forcent à se révéler.
**À exploiter** : sauver TOUS les alliés engagés (Force of Will = secondes gratuites) ; les portails = rotations impossibles à intercepter ; Ley Line = setup de combo.
**Pièges** : il est inutile si le joueur ne voit pas les engages — la micro de protection est son tout ; Poly Bomb se propage, mais se disperse si l'adversaire joue éparpillé.
**Synergies** : les combos murs (Diablo, Garrosh), les dives (Illidan, Genji — portail de sortie), E.T.C. (portail + Mosh).
""",
"mei": """**Rôle** : tank de contrôle — Blizzard de zone, walls (Ice Wall / Avalanche), lenteur constante.
**Menaces** : % damage (Tychus, Malthael) ; kiting (elle est lente à l'engage) ; les compo qui passent ses walls.
**À exploiter** : les zones d'objectif (son Blizzard les verrouille) ; les compo groupées (Avalanche = pick) ; le peel de son backline (walls).
**Pièges** : ses walls bloquent AUSSI son équipe — les placer pour l'adversaire, pas contre les alliés ; son engage est lent, jouer en contre.
**Synergies** : bursts de zone (Kael'thas, Jaina, Gul'dan), setups (Garrosh throw dans ses walls), compo de point (Volskaya, Braxis).
""",
"mephisto": """**Rôle** : assassin de zone — AoE en chaîne, Durance of Hate (ult de root de zone), teleport de trait.
**Menaces** : dive rapide (il est squishy hors de son trait) ; les compo éparpillées (ses dégâts exigent des groupes) ; burst pendant son teleport en CD.
**À exploiter** : les compo groupées (ses chaînes de dégâts) ; les zones de choke ; les teamfights longues où son trait lui donne de la mobilité.
**Pièges** : ses dégâts sont nuls sur cibles isolées — forcer les teamfights groupées, pas les duels ; Durance se dodge en restant éparpillé.
**Synergies** : setups de regroupement (Johanna, E.T.C. Mosh), slows (Arthas), Auriel (ses dégâts de zone = Hope).
""",
"muradin": """**Rôle** : tank polyvalent — jump (engage/escape), stun (Storm Bolt), Avatar (ult de tankage).
**Menaces** : % damage (Tychus, Malthael) ; kiting (Storm Bolt est son seul accroche) ; les compo qui le ignorent (son dégât est faible).
**À exploiter** : les picks (jump + bolt + burst sur backline) ; le peel (bolt sur le diveur) ; l'engage sur les mages.
**Pièges** : son jump est aussi son escape — jamais premier sans follow-up ; Thunder Clap (slow) est sous-estimé, le garder pour le bon moment.
**Synergies** : bursts d'entrée (Li-Ming, Kael'thas, Jaina), Uther (DS), setups (son bolt = combo de toute l'équipe).
""",
"murky": """**Rôle** : macro absurde — œuf (respawn en 8 s), split-push, Octograb (ult de lock mono-cible).
**Menaces** : les chasseurs d'œuf (trouver et tuer l'œuf = Murky neutralisé) ; les clear de wave rapides (Junkrat, Xul, Kael'thas).
**À exploiter** : le split permanent (il meurt « gratuitement ») ; les maps à 3 lanes ; Octograb = pick garanti sur une cible.
**Pièges** : cacher l'œuf est la priorité absolue ; nourrir de l'XP en mourant trop = donner de l'avantage — mourir sert, pas mourir pour rien.
**Synergies** : Abathur (hat sur Murky = macro absurde), globals (Dehaka, Falstad), Octograb + burst (Li-Ming).
""",
"nazeebo": """**Rôle** : mage de late-game — stacks de trait (dégâts qui montent), zones (spiders, zombie wall), Gargantuan.
**Menaces** : dive tôt (il est faible avant ses stacks) ; les compo qui finissent la game avant 20 ; anti-heal (son heal de trait).
**À exploiter** : les parties longues (ses stacks = un mage de plus en plus gros) ; les zones de choke (zombie wall) ; les maps à minion de zone.
**Pièges** : ses stacks se font en early sur les minions — le joueur DOIT last-hit ; zombie wall bloque les alliés aussi.
**Synergies** : Auriel (Hope infinie en late), setups de zone (Johanna, Garrosh), comps qui traînent la game (Murky, Abathur).
""",
"nova": """**Rôle** : assassin de pick — invisibilité, snipe longue portée, Precision Strike.
**Menaces** : la vision (Tyrande, Medivh, Hanzo Sonic, Wisp de Lunara, les drones) ; les tanks qui absorbent son burst ; les compo groupées.
**À exploiter** : les squishies isolés (Ana, Li-Ming, Chromie) ; les rotations de backline ; les maps avec des flanks (Warhead, Cursed).
**Pièges** : elle ne push rien et ne clear rien — son équipe joue à 4 en macro ; révéler sa position = perdre sa seule force.
**Synergies** : setups de stun (Muradin, E.T.C.) qui garantissent son snipe, vision alliée (Medivh), Abathur (hat = snipe garanti).
""",
"orphea": """**Rôle** : assassin de combo mobile — dash de trait (Crimson Rush), burst de zone, Eternal Feast.
**Menaces** : kiting (elle doit être en mêlée pour son trait) ; les compo qui la punissent quand elle dash ; blinds.
**À exploiter** : les compo groupées (son burst de zone) ; les cibles immobiles (son combo se place) ; les zones de choke.
**Pièges** : son dash est aussi sa survie — le réserver pour esquiper, pas pour engager ; Eternal Feast est bestial en zone mais nul sur cible isolée.
**Synergies** : setups de regroupement (Johanna, E.T.C., Garrosh), Medivh (protection pendant ses combos), Auriel (dégâts = heal).
""",
}
