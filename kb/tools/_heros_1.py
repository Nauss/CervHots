# kb/tools/_heros_1.py — fiches héros (couche jugement), lot 1/3 (a-g).
# Données pures ; l'écriture des .md est faite par seed_heros.py.

HEROS = {
"abathur": """**Rôle** : enable global — Symbiote sur allié, macro XP permanente, split-push.
**Menaces** : chasseurs de body (Nova, Zeratul, Genji, Valeera) ; globals adverses (Falstad, Dehaka) qui annulent son split ; burst sur le corps isolé.
**À exploiter** : XP et présence permanente (hat + corps en même temps) ; chaque duel devient un 2v2 ; les maps à 3 lanes.
**Pièges** : le corps reste exposé sur une lane — le placer en sécurité avant chaque teamfight ; le hat demande de la micro continue, un hat « oublié » gâche tout.
**Synergies** : hypercarries all-in (Illidan, The Butcher, Varian, Kerrigan, Greymane, Tracer) — le hat les rend invincibles.
""",
"alarak": """**Rôle** : assassin mêlée — burst de combo (Discord Strike = silence), displacement, Sadisme qui monte.
**Menaces** : kite et portée (Lunara, Valla, Raynor, Li-Ming) ; blinds (Johanna, Cassia, Li Li) ; CC long (Uther, Muradin) ; Cleanse qui casse son combo.
**À exploiter** : tanks immobiles (Stitches, Arthas) qu'il punit ; les compo qui viennent à lui (counter-engage) ; les zones étroites.
**Pièges** : combo raté = il est en mêlée sans rien ; ses stacks de Sadisme se perdent en partie à la mort — pas de duel inutile.
**Synergies** : E.T.C. (Mosh + combo), Johanna (pull = combo garanti), Medivh (portail + protection).
""",
"alexstrasza": """**Rôle** : support de zone — heals en AoE, forme Dragonqueen, Lifebinder.
**Menaces** : anti-heal (Biotic Grenade d'Ana) ; burst ciblé sur elle (Genji, Zeratul, Valeera) ; dive qui la force hors position.
**À exploiter** : teamfights rangées et objectifs fixes (ses zones de soin) ; les longs engagements où ses heals cumulés gagnent.
**Pièges** : Lifebinder sur un allié déjà bas = soin faible ; Dragonqueen est puissante mais la place au premier plan — timing de transform.
**Synergies** : compo groupées (Johanna, Blaze, Mei), hypercarries (Valla, Raynor) qui profitent de Gift of Life.
""",
"ana": """**Rôle** : support longue portée — heals de précision, Biotic Grenade (anti-heal ennemi + amplification alliée), Sleep Dart.
**Menaces** : dive sans peel (Genji, Tracer, Zeratul, Valeera) ; les shields qui absorbent ses heals ; alliés mobiles qui rendent ses tirs impossibles.
**À exploiter** : les compo sustain ennemies (grenade anti-heal pendant leur heal window) ; tanks immobiles qui prennent des dégâts prévisibles.
**Pièges** : sans peel elle meurt en 2 s ; Nano Boost ne vaut que sur un bon récepteur (mage burst) — le poser par défaut = gaspillage.
**Synergies** : hypercarries à Nano (Kael'thas, Gul'dan, Valla, Hanzo), tanks immobiles (Johanna, Diablo, Garrosh).
""",
"anduin": """**Rôle** : support — sauvegarde (Leap of Faith = traction d'un allié), counter-engage (Lightbomb), heals fiables.
**Menaces** : dive coordonné (ses heals sont réactifs, pas préventifs) ; silence/burst pur (Brightwing, Uther, Valeera).
**À exploiter** : sauver l'allié attrapé par un Garrosh/Stitches/Diablo (Leap annule leur pick) ; Lightbomb en counter-engage sur un engage adverse.
**Pièges** : Leap of Faith a un long CD — ne le gaspiller que sur la vraie menace ; Lightbomb sur un allié immobile est souvent mieux que sur le tank qui charge.
**Synergies** : mages immobiles attrapables (Kael'thas, Gul'dan, Chromie), tanks qui engagent (Garrosh, Diablo, Anub'arak).
""",
"anubarak": """**Rôle** : tank d'engage anti-mage — Burrow Charge, Cocoon (ult de mise à l'écart), scarabées.
**Menaces** : dégâts automatiques et % damage (Tychus, Valla, Butcher, Malthael) — il est le tank le plus « papier » ; CC chain sur son retour d'engage.
**À exploiter** : les compo mages (Cocoon sur le healer = 8 s de 5v4, ou sur le mage) ; engage instantané sur backline.
**Pièges** : il est fragile hors engage — jamais premier sans follow-up ; Cocoon mal chronométré (sur un tank déjà bas) = ult perdu.
**Synergies** : burst d'entrée (Li-Ming, Kael'thas, Jaina), Medivh (portail de sortie), Uther (Divine Shield sur son engage).
""",
"artanis": """**Rôle** : bruiser de duel — shields de survie, Blind (Suppression Pulse), swap (Phase Prism).
**Menaces** : % damage (Tychus, Malthael) ; kiting (Lunara, Valla, Raynor) ; CC chain qui empêche ses shields de revenir.
**À exploiter** : les compo auto-attacks (son blind est dévastateur) ; la tenue de point (il ne meurt jamais en 1v1 propre) ; swap sur un squishy au bord du groupe.
**Pièges** : swap raté ou sur la mauvaise cible = position compromise ; il ne peel rien pour son équipe — il faut un vrai tank à côté.
**Synergies** : burst de follow-up (Li-Ming), Medivh (portail), setups murés (swap sous son propre mur sur les bonnes maps).
""",
"arthas": """**Rôle** : tank anti-auto-attacks — aura de slow (Frostmourne), Ghouls, Icebound Fortitude.
**Menaces** : mages (Jaina, Kael'thas, Li-Ming — il est lent) ; % damage (Tychus, Malthael) ; kite permanent (Lunara, Raynor).
**À exploiter** : les carries auto-attacks (Illidan, Butcher, Valla, Greymane, Zul'jin) qu'il rend inutiles ; les dives qui viennent à lui.
**Pièges** : pas de stun, pas d'engage — c'est un anti-dive, pas un initiateur ; le jouer en premier = il se fait kiter toute la game.
**Synergies** : vrai tank d'engage à côté (Muradin, Diablo, Garrosh), heals de zone (Stukov, Deckard).
""",
"auriel": """**Rôle** : support à énergie (Hope) — ses heals dépendent des dégâts du porteur de sa Couronne.
**Menaces** : anti-heal (Ana) ; burst sur le porteur de couronne ; dive sur elle (elle n'a pas de dash).
**À exploiter** : les hypercarries à dégâts constants (Valla, Kael'thas, Gul'dan, Zul'jin, Nazeebo) = heal infini ; les longues teamfights.
**Pièges** : sans bon porteur de couronne, ses heals sont médiocres — choisir le porteur selon la compo, pas par habitude ; Crystal Aegis mal placé emprisonne un allié pour rien.
**Synergies** : Valla, Kael'thas, Gul'dan, Zul'jin, Nazeebo, Cho'gall (Gall = moteur de Hope).
""",
"azmodan": """**Rôle** : siege et poke longue portée — Globe stacké, démons de trait, Demonic Invasion.
**Menaces** : dive (Genji, Zeratul, Tracer — il est énorme et lent) ; engage de pick (Garrosh, Anub'arak, Stitches) ; heals qui absorbent son poke.
**À exploiter** : les maps à 3 lanes (Tomb, Warhead) ; les compo sans engage ; le poke de siège avant les objectifs.
**Pièges** : ses globes ne font mal qu'avec des stacks accumulées tôt (last-hit au Q en early) ; Demonic Invasion se clear vite si l'équipe n'est pas là.
**Synergies** : vision pour ses globes (Tyrande, Medivh, Hanzo), setups de pull (Johanna, Garrosh), Abathur (double push).
""",
"blaze": """**Rôle** : tank bruiser — huile + brûlure, Jet Propulsion (stun en ligne), Bunker (ult de sauvegarde d'équipe).
**Menaces** : kiting (son engage est télégraphié et court) ; % damage (Tychus, Malthael) ; purges qui nettoient son huile.
**À exploiter** : les compo auto-attacks (slow d'huile + blind de Bunker) ; les zones d'objectif ; le Bunker pour annuler un ult adverse (Molten Core, Pyroblast…).
**Pièges** : Jet Propulsion s'arrête au premier mur/minion — viser les lignes ouvertes ; le Bunker mal chronométré sort tout le monde du combat pour rien.
**Synergies** : AoE de follow-up (Kael'thas, Gul'dan, Mephisto), compo qui reste groupée (Stukov, Deckard).
""",
"brightwing": """**Rôle** : support global — teleport (Z), Polymorph (anti-carry), Soothing Mist passive.
**Menaces** : dive ciblé (elle est squishy) ; burst pur que son heal lent ne suit pas ; anti-heal (Ana).
**À exploiter** : les dives adverses (Polymorph sur Illidan, Genji, Varian, Butcher = leurs all-in deviennent un suicide) ; les maps à grandes rotations (global).
**Pièges** : son heal est passif et faible — il faut rester collé au groupe ; Emerald Wind la place au centre du combat, à réserver pour le vrai peel.
**Synergies** : hypercarries protégées par Polymorph (Illidan, Varian, Butcher alliés), split-pushers (le global suit), Genji.
""",
"cassia": """**Rôle** : assassin ranged anti-auto-attacks — Blind, Fend (execute en mêlée), dégâts qui montent sur cibles blessées.
**Menaces** : kiting (Lunara, Valla, Raynor — pas de dash) ; burst mage (Li-Ming, Jaina) ; stun-lock qui casse son passif de mobilité.
**À exploiter** : les compo auto-attacks (Illidan, Butcher, Valla, Zul'jin rendus aveugles) ; les tanks qui viennent à elle (Fend).
**Pièges** : sa survie dépend de bouger constamment (passif) — s'arrêter pour un auto = mourir ; Fend est risqué, jamais en premier.
**Synergies** : slows et stuns (Johanna, Arthas, Muradin) pour poser ses autos, Auriel (ses dégâts nourrissent son heal).
""",
"chen": """**Rôle** : bruiser d'immortalité — trait de boisson (shield), disruption du backline, Wandering Keg.
**Menaces** : CC chain qui interrompt sa boisson (stuns surtout) ; % damage (Tychus, Malthael) ; blinds ; les compo qui le ignorent et killent le reste.
**À exploiter** : les compo sans stun (il est quasi immortel) ; l'isolement du backline adverse pendant que les 4 autres gagnent le front.
**Pièges** : boire sans couverture = shield cassé en 2 s ; le Keg isole un ennemi mais laisse son équipe en 4v4 — le bon timing est clé.
**Synergies** : heals de soutien (Lt. Morales, Ana), burst qui finit la cible qu'il isole (Li-Ming).
""",
"chogall": """**Rôle** : duo — Cho (tank/pilote) + Gall (dégâts à distance) : un seul corps, deux joueurs.
**Menaces** : % damage (Tychus, Malthael) ; kiting (Cho est lent — Lunara, Valla) ; CC chain sur Cho = les deux neutralisés.
**À exploiter** : les teamfights groupées (l'AoE de Gall) ; les objectifs fixes ; les maps où il peut tanker deux rôles à la fois.
**Pièges** : une mort = deux joueurs hors jeu ; il exige une vraie coordination Cho/Gall ; les compo qui le kiten le rendent inutile.
**Synergies** : Auriel (Gall = moteur de Hope), Uther (armure), Medivh (portail = son seul vrai dash).
""",
"chromie": """**Rôle** : mage longue portée — burst télégraphié (Sand Blast), pièges de vision (Time Trap), Temporal Loop.
**Menaces** : dive rapide (Genji, Zeratul, Tracer, Illidan — elle est squishy et son burst est différé) ; les tanks qui absorbent son poke ; Cleanse (annule Temporal Loop).
**À exploiter** : les compo lentes (Arthas, Stitches, Azmodan) ; les zones de choke d'objectif ; les cibles prévisibles.
**Pièges** : Sand Blast se dodge — viser les cibles CC-ées ou déjà engagées ; Temporal Loop ne vaut que si le burst suit dans la seconde.
**Synergies** : setups de stun (Muradin, E.T.C., Diablo), vision (Tyrande, Medivh), Uther (DS = combo garanti).
""",
"deathwing": """**Rôle** : tank bruiser — deux formes (World Breaker / Destroyer), immune aux CC, vol entre les lanes.
**Menaces** : % damage (Tychus, Malthael — il est immense) ; kiting (sa taille le rend facile à taper) ; focus quand il atterrit.
**À exploiter** : les compo CC-heavy (il est totalement immune) ; le chaos d'atterrissage sur backline ; le split multi-lane (vol).
**Pièges** : il ne peut PAS être soigné par ses alliés — sa vie se gère en régénération et en positionnement ; tanker le monde entier = juste un gros pourcentage pour Tychus.
**Synergies** : Li-Ming (resets sur le chaos qu'il crée), solo-laners qui le libèrent de sa lane (Yrel, Blaze).
""",
"deckard": """**Rôle** : support de zone — potions pré-posées, Horadric Cube (slow), Stay Awhile (sommeil d'équipe).
**Menaces** : dive ciblé (il est lent et sans dash) ; anti-heal (Ana) ; les compo qui jouent mobiles (ses potions sont fixes).
**À exploiter** : les zones de combat fixes (potions posées avant l'objectif) ; les compo groupées ; Stay Awhile pour disengage ou pick.
**Pièges** : potions ratées ou posées trop tard = heal inexistant ; son ult est channel — l'interrompre annule tout.
**Synergies** : tanks de zone (Johanna, Blaze, Mei), objectifs fixes (Shrines, Volskaya, Braxis).
""",
"dehaka": """**Rôle** : bruiser global — burrow (Z), Drag (isolation d'une cible), régénération dans les buissons.
**Menaces** : vision (Tyrande, Medivh — il vit dans les buissons) ; % damage (Tychus, Malthael) ; kiting (Drag est court).
**À exploiter** : les grandes maps (son global change les fights en nombre) ; le split-push qui rejoint le groupe ; les picks (Drag + burst).
**Pièges** : Isolation ne silencie qu'une cible — choisir le bon (le healer, pas le tank) ; son Z arrive avec un délai, pas un escape instantané.
**Synergies** : double global (Falstad, Brightwing), burst qui finit la cible draguée (Li-Ming, Jaina).
""",
"diablo": """**Rôle** : tank de combo murs — Shadow Charge + Overpower, résurrection par soulstones, Apocalypse.
**Menaces** : % damage (Tychus, Malthael) ; kiting (il est tout ou rien) ; les maps ouvertes sans murs proches (ses combos exigent un mur).
**À exploiter** : les combos murs (charge + overpower sous le mur = kill garanti) ; les squishies en position limite ; les choke points.
**Pièges** : sous 100 soulstones il est nettement plus faible — ne pas le jeter en early ; ses combos se préparent, ils ne s'improvisent pas.
**Synergies** : burst d'exécution (Li-Ming, Kael'thas, Jaina), Medivh (portail = combos infinis), Anduin (sauvegarde après engage).
""",
"dva": """**Rôle** : tank bruiser à deux vies — MEKA (tank) puis pilote (DPS fragile), Self-Destruct.
**Menaces** : % damage sur la MEKA (Tychus, Malthael) ; focus du pilote hors MEKA ; CC chain qui empêche de rembarquer.
**À exploiter** : les longs combats (elle « reset » en sortant puis remonte une MEKA) ; les zones d'objectif (Self-Destruct les verrouille).
**Pièges** : Boosters gaspillés = MEKA perdue en 3 s ; le pilote doit rester vivant et taper pour recharger une MEKA — jouer trop prudent = équipe à 4.
**Synergies** : heals de soutien (Lt. Morales, Ana), setups pour Self-Destruct (E.T.C. Mosh, Johanna pull, Garrosh throw).
""",
"etc": """**Rôle** : tank d'engage — Mosh Pit (ult de contrôle d'équipe), Face Melt (peel/displacement), Stage Dive.
**Menaces** : interrupts (tout stun/silence annule Mosh) ; % damage (Tychus) ; kiting (il est squishy pour un tank).
**À exploiter** : les compo groupées (Mosh = teamfight gagnée) ; le peel anti-dive (Face Melt) ; les maps avec des flanks (Stage Dive).
**Pièges** : Mosh sans vision de leurs interrupts = coin flip à 50 % ; Power Slide est sa vie — ne le gaspiller pour voyager.
**Synergies** : burst de zone pendant Mosh (Kael'thas, Jaina, Li-Ming, Mephisto), Medivh (portail de placement), Anduin (Lightbomb en double CC).
""",
"falstad": """**Rôle** : assassin ranged global — flight (Z), poke en chaines, Gust (ult de reset de combat).
**Menaces** : dive rapide (Genji, Zeratul, Tracer) ; stun (il est squishy) ; vision qui révèle ses flanks.
**À exploiter** : les grandes maps (global = première à chaque objectif) ; Gust pour sauver un allié ou séparer une équipe adverse ; le poke de lane.
**Pièges** : Gust mal placé sauve l'ennemi (le pousser DANS son équipe est l'idéal) ; son global met du temps — l'anticiper, pas le réagir.
**Synergies** : double global (Dehaka, Brightwing), setups de zone (Johanna pull + son poke), combos Gust + engage.
""",
"fenix": """**Rôle** : assassin ranged — shields régénérants, Warp (dash), Planet Cracker (beam global).
**Menaces** : burst qui casse ses shields d'un coup (Li-Ming, Kael'thas, Jaina) ; blinds sur ses autos ; interrupt sur Planet Cracker.
**À exploiter** : les longs combats (ses shields reviennent en continu) ; les compo sans burst ; le poke de lane avec son plasma.
**Pièges** : Warp est son seul escape — ne jamais s'engager sans lui ; Planet Cracker est un channel : le poser quand leurs interrupts sont déjà utilisés.
**Synergies** : vision pour son beam (Tyrande, Medivh), setups de CC (E.T.C., Muradin), Auriel (ses dégâts = son heal).
""",
"gall": """**Rôle** : DPS ranged — contrôlé par le joueur de Cho : burst d'orb, zone, Shove (protection de Cho).
**Menaces** : tout ce qui tue Cho ; kiting (il ne choisit jamais sa position) ; les compo qui ignorent Cho et oneshotent le groupe.
**À exploiter** : sa position toujours « derrière le tank » = dégâts gratuits en continu ; les zones serrées (ses orb).
**Pièges** : il ne dépend que de Cho — communiquer ; Shove est le seul peel du duo, le réserver pour les vrais engages.
**Synergies** : identiques à Cho — Auriel (Hope), Uther (armure), Medivh (portail).
""",
"garrosh": """**Rôle** : tank de pick — Groundbreaker (pull), Wrecking Ball (throw d'ennemi hors position), Taunt.
**Menaces** : kiting extrême (il est le tank le plus lent) ; % damage (Tychus, Malthael) ; les compo ranged qui le tapent sans qu'il accroche.
**À exploiter** : les picks (throw un ennemi dans son équipe = kill instantané) ; les compo melee qui viennent à lui ; les choke points.
**Pièges** : sans accroche il ne fait rien — il lui faut un angle ; throw un tank vivant dans son équipe peut sauver l'ennemi.
**Synergies** : burst sur le throwé (Li-Ming, Kael'thas, Jaina), Anduin (Leap de sauvetage), E.T.C. (double displacement).
""",
"gazlowe": """**Rôle** : bruiser de zone — tourelles, Gravo-Bomb, Robo-Goblin (tank de siège).
**Menaces** : clear de tourelles (Junkrat, Hanzo, Azmodan) ; dive direct sur lui (Genji, Zeratul) ; % damage.
**À exploiter** : les objectifs fixes (ses tourelles verrouillent une zone) ; le push de siège ; les zones de choke.
**Pièges** : ses tourelles se font clear en 2 s si l'équipe adverse s'y met — les replacer en combat ; rester collé à son setup sans quoi il ne fait rien.
**Synergies** : setups pour Gravo-Bomb (E.T.C. Mosh, Johanna pull, Garrosh throw), vision (ses tourelles), Abathur (double siège).
""",
"genji": """**Rôle** : assassin de reset — Swift Strike (reset sur kill), sauts de mur, X-Strike / Dragonblade.
**Menaces** : CC de point-and-click (Uther, Muradin, Brightwing Polymorph) ; Arthas (slow sans fin) ; toute compo qui garde ses interrupts pour son ult.
**À exploiter** : les backlines squishies (Li-Ming, Chromie, Ana) ; finir les kills pour enchaîner les resets ; les sorties de terrain (il passe partout).
**Pièges** : il entre et DOIT sortir — sans reset il meurt ; Dragonblade est un channel : le poser quand les stuns sont down.
**Synergies** : Abathur (hat = double dive), Medivh (portail de sortie), Uther (Divine Shield = all-in sûr).
""",
"greymane": """**Rôle** : assassin hybride — poke ranged (forme humaine), execute mêlée (forme Worgen), Cursed Bullet (% damage).
**Menaces** : blinds (ses autos humaines) ; CC en forme Worgen (il doit rester collé) ; kiting en sortie d'execute.
**À exploiter** : les tanks (Cursed Bullet = % de PV actuels) ; les kills à finir (Worgen execute) ; la prise de camps (rapide).
**Pièges** : le all-in Worgen sans sortie = mort ; Cursed Bullet ne finit pas un kill tout seul (dégâts sur PV actuels).
**Synergies** : Abathur (hat), Uther (DS sur l'execute), E.T.C./Garrosh (engage qu'il suit), Auriel (dégâts = heal).
""",
"guldan": """**Rôle** : mage de zone — Corruption (DoT AoE), Life Tap (sa vie = sa mana), Horrify (fear d'équipe).
**Menaces** : dive (il est lent et sa vie est sa ressource) ; anti-heal (Ana) ; les compo qui le forcent à Life Tap en danger.
**À exploiter** : les compo groupées (Corruption full stack) ; les longs combats (mana infini) ; les choke points.
**Pièges** : Life Tap en position exposée = kill offert ; Horrify mal placé fait fuir l'ennemi HORS de votre burst (comme un mauvais Gust).
**Synergies** : Auriel (ses dégâts = heal permanent), setups de pull (Johanna, Garrosh), Uther (armure qui couvre son Life Tap).
""",
}
