#!/usr/bin/env python3
"""kb/tools/seed_cartes.py — remplissage initial des fiches de carte.

Les fiches de la couche jugement sont rédigées ici (LLM, 12/10/2026) puis
écrites dans kb/notes/cartes/<slug>.md. APRÈS usage, les fiches s'éditent
DIRECTEMENT dans notes/cartes/ ; ce script n'est qu'une graine (rejouer =
écraser les modifications manuelles).

Usage : python kb/tools/seed_cartes.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "notes", "cartes")

HEADER = (
    "> Fiche rédigée par LLM le 12/10/2026 — **à relire** (couche jugement).\n"
    "> Les timings chiffrés vivent dans `kb/data/map_timings.json`, pas ici.\n"
)

CARTES = {
    "infernal-shrines": """# Les sanctuaires infernaux — Infernal Shrines

**Objectif** : capter un sanctuaire (tuer 40 gardiens) avant l'équipe adverse → un Punisher invoqué pousse la lane du sanctuaire.
**Plan de jeu** : arriver avant l'annonce finie ; le sanctuaire est une zone étroite = les AoE et le contrôle y valent plus que le bruit. Une fois le Punisher pris, pousser AVEC lui (il saute les murs), pas derrière.
**Pièges** : rester sur le sanctuaire avec 3 héros pendant que l'adversaire split deux lanes ; contester un sanctuaire à 10 % vs 90 % plutôt que de prendre l'XP et la wave suivante ; défendre devant le mur contre le Punisher (il saute par-dessus).
**Héros qui marchent bien** : gros AoE de zone (Kael'thas, Gul'dan, Junkrat), heals de zone (Stukov, Deckard), tanks à contrôle de foule dense (Johanna, Arthas, Blaze).
""",
    "cursed-hollow": """# Le val maudit — Cursed Hollow

**Objectif** : 3 tributs = malédiction 70 s : minions ennemis à 1 PV et fortifications muettes. Fenêtre de destruction gratuite.
**Plan de jeu** : le tribut est aléatoire — le 1er est contestable à 3:00, puis cycle court (observé dès ~1 min, jusqu'à 2 min) après chaque cap. Jouer en 4-1 ou 1-3-1 selon la position du tribut : prendre des structures et de l'XP pendant la malédiction plutôt que de courir après les kills. Channel du tribut : 5 s.
**Pièges** : donner le 3e tribut « pour un kill » ; se battre sur un tribut alors que la malédiction adverse est déjà gagnée ; oublier que les forts sont muets pendant la malédiction (les défendre en solo est un suicide).
**Héros qui marchent bien** : globaux et split-pushers (Dehaka, Falstad, Abathur, Zagara) qui capitalisent sur la malédiction ; voleurs de tribut (Zeratul, Tracer, Genji, Medivh) ; tank à engage court (Anub'arak, Muradin).
""",
    "garden-of-terror": """# Les jardins de terreur — Garden of Terror

**Objectif** : la nuit tombe, des graines apparaissent partout sur la carte (3 par monstre, 100 au total). Chaque équipe qui a collecté des graines reçoit un Terreur de Jardin pilotable.
**Plan de jeu** : la collecte est un jeu de split et de rotation, pas de teamfight groupé — les camps de nuit et les packs de graines se font en parallèle. Viser 55+ graines pour avoir le Terreur le plus fort, puis pousser avec (il pose des pots qui ralentissent et shoothe les structures).
**Pièges** : tout le groupe qui tourne ensemble sur les graines (on perd du temps mort) ; ignorer le Terreur adverse qui pousse pendant qu'on finit la collecte ; ne pas garder une vision sur les packs du centre.
**Héros qui marchent bien** : clear rapide et mobilité (Fenix, Hanzo, Junkrat, Zagara, Dehaka), bons duels 1v1 pour sécuriser un pack (Illidan, Sonya, Alarak), voleurs de graines (Tracer, Zeratul).
""",
    "dragon-shire": """# Le comté du dragon — Dragon Shire

**Objectif** : tenir l'autel haut ET l'autel bas, puis canaliser au centre (3 s) = Chevalier Dragon (55 s + 2 s/min de jeu) qui pousse une lane.
**Plan de jeu** : c'est une carte de présence, pas de kills. Garder un héros par autel, le reste en rotation rapide entre haut et bas. Le DK se gagne en créant un déséquilibre local (3v2 sur un autel) plutôt qu'en teamfight totale. Cycle : 120 s après la mort du DK.
**Pièges** : quitter un autel pour un kill « gratuit » (l'autel bascule en 2-3 s de décap) ; canaliser le DK sans avoir sécurisé les deux autels ; ne pas réagir à la durée du DK (il est plus long en fin de partie).
**Héros qui marchent bien** : grands duels de lane (Yrel, Blaze, Dehaka, Sonya), mobilité de rotation (Falstad, Brightwing, Genji), contrôle de zone sur les autels (Junkrat, Stitches, Medivh).
""",
    "alterac-pass": """# La passe d'Alterac — Alterac Pass

**Objectif** : capter 2 des 3 bunkers (channel 3 s, cap 30 s +10 s par bunker déjà pris) = Cavalerie qui pousse ; les bunkers capturés donnent aussi des points de vie au camp.
**Plan de jeu** : viser le couple de bunkers le plus proche de votre rotation, y aller à plusieurs (le cap est long). Le cycle accélère avec le temps (−2 s/min), donc les premiers objectifs valent plus cher : ne pas « économiser » ses ults pour plus tard.
**Pièges** : solo-capter un bunker (30 s = une éternité) ; ignorer la Cavalerie adverse pendant qu'on recapte un bunker ; sous-estimer la régénération des bunkers en défense.
**Héros qui marchent bien** : tanky et contrôle (Johanna, Garrosh, Muradin), sustain de zone pour tenir le cap (Deckard, Stukov, Whitemane), DPS à la cible fixe (Valla, Tychus, Hanzo).
""",
    "hanamura-temple": """# Le temple d'Hanamura — Hanamura Temple

**Objectif** : escorter les convois (payloads) jusqu'à leur destination ; un convoi qui avance tire sur les structures ennemies.
**Plan de jeu** : les convois sont une course de rotation : les waves non clearées ralentissent le convoi, donc clear avant de pousser le point. Tenir la zone autour du convoi plutôt que de chasser. Le compteur du prochain convoi repart 150 s après l'arrivée, même si le tir continue.
**Pièges** : laisser une wave adverse bloquer le convoi ; overcommit sur le convoi pendant que l'adversaire split la seconde voie de convoi ; oublier les camps (ils poussent très bien sur cette carte).
**Héros qui marchent bien** : clear de wave (Junkrat, Gul'dan, Xul, Fenix), zone de contrôle autour du convoi (Mei, Blaze, Arthas), heals de zone longue durée (Lucio, Stukov, Deckard).
""",
    "volskaya-foundry": """# La fonderie Volskaya — Volskaya Foundry

**Objectif** : tenir le point de contrôle jusqu'à 100 % (52 s, overtime 5 s) = Protecteur pilotable (2 places : un pilote, un tireur).
**Plan de jeu** : le cap est continu : rester dans la zone, y compris sur les zones de soin périphériques qui comptent. Le Protecteur est un bélier : l'utiliser pour une structure majeure (fort/keep), pas pour un duel. Durée : 50 s + 3 s/min.
**Pièges** : quitter la zone pour poursuivre un kill (le cap tombe vite) ; envoyer le Protecteur seul sans les waves ; ignorer le second objectif pendant qu'on pilote.
**Héros qui marchent bien** : tenue de point (Mei, Johanna, Blaze, Yrel), AoE anti-foule (Kael'thas, Gul'dan, Mephisto), soins de zone (Lucio, Auriel, Stukov).
""",
    "towers-of-doom": """# Les tours du destin — Towers of Doom

**Objectif** : capter les autels (channel 5 s) qui tirent sur le Cœur ennemi ; le Cœur ne peut être touché que par les tirs, pas par les héros.
**Plan de jeu** : carte de contrôle d'autels et de tours — les kills ne font que dégager la voie. Compter les tirs : chaque autel tirant une fois par tour possédée, une équipe à 4 tours peut « voler » une partie. À 12:00 : tunnel bas-centre ouvert + tour améliorée.
**Pièges** : se focaliser sur les kills alors que l'adversaire capte les autels ; ne pas surveiller le compteur de tours (3-1 = un autel peut faire mal) ; oublier le tunnel après 12:00 (les rotations bas deviennent rapides).
**Héros qui marchent bien** : contrôle de zone et vols d'autel (Zeratul, Medivh, Tracer, Genji), tanks à engage (Diablo, Garrosh — punir le cap), poke longue portée (Hanzo, Chromie, Junkrat).
""",
    "battlefield-of-eternity": """# Les champs de l'éternité — Battlefield of Eternity

**Objectif** : deux Immortels s'affrontent ; l'équipe qui inflige le plus de dégâts garde son Immortel (avec un bouclier) qui pousse une lane.
**Plan de jeu** : c'est une course de DPS à deux fronts : gros dégâts sur l'Immortel adverse, contrôle sur leurs meilleurs DPS. L'Immortel met 15 s à sortir : on peut déjà pousser la wave de la lane visée. Après la mort de l'Immortel : 105 s avant le prochain duel.
**Pièges** : tanker l'Immortel ennemi dans sa zone (dégâts de zone), tout le monde en race sans protéger les flancs, ou l'inverse (teamfight pendant que l'adversaire race tranquillement).
**Héros qui marchent bien** : DPS à cible unique (Valla, Tychus, Greymane, Hanzo, Fenix), contrôle anti-race (Anub'arak, Muradin, E.T.C.), soins de soutien long (Malfurion, Ana, Lt. Morales).
""",
    "tomb-of-the-spider-queen": """# La tombe de la reine araignée — Tomb of the Spider Queen

**Objectif** : rapporter des gemmes au centre (tour ouvert dès 0:30) = Tisseuses d'Arachnides qui poussent les 3 lanes ; les gemmes reviennent 15 s après la mort des Tisseuses.
**Plan de jeu** : la carte est petite et la collecte se fait en tuant — le clear de wave est roi. Tourner tôt (2 tours de gemmes) quand l'adversaire est dispersé est souvent meilleur qu'attendre 14 gemmes par héros. Mourir = perdre ses gemmes : la discipline de survie prime sur les duels.
**Pièges** : stocker 20+ gemmes et mourir en duel ; laisser l'adversaire tourner en 4 pendant qu'on clear sans vision ; ignorer les Tisseuses (elles perdent 100 PV/s mais poussent fort).
**Héros qui marchent bien** : clear et waveclear rapide (Xul, Gul'dan, Kael'thas, Junkrat, Nazeebo), bons à survivre/se cacher (Zeratul, Tracer, Medivh), poke de défense de Tisseuses (Sgt. Hammer, Hanzo, Chromie).
""",
    "sky-temple": """# Le temple céleste — Sky Temple

**Objectif** : tenir les temples qui apparaissent (2, puis 2, puis 3...) : chaque temple tenu tire sur les structures ennemies les plus proches.
**Plan de jeu** : le cap est continu (40 s pour 100 %) : rester dans la zone, pas la quitter pour un kill. Rotation rapide entre les deux temples du début : une équipe mobile split 3-2 mieux qu'un groupe de 5 qui court. Les tirs visent les structures proches : garder les murs sains fait changer la cible.
**Pièges** : overcommit sur un temple pendant que l'adversaire prend l'autre tranquillement ; ne pas clear les waves proches des temples (les tirs tombent sur les structures, les minions finissent le travail) ; oublier que les temples du milieu arrivent en fin de partie.
**Héros qui marchent bien** : mobilité de rotation (Falstad, Dehaka, Brightwing, Genji), tenue de zone (Johanna, Blaze, Mei), DPS sûr et longue portée (Hanzo, Fenix, Li-Ming).
""",
    "braxis-holdout": """# Le laboratoire de Braxis — Braxis Holdout

**Objectif** : tenir 2 balises sur 2 (cap complet 37,5 s) = vague de Zerg qui pousse une lane (jusqu'à 100 % de puissance).
**Plan de jeu** : deux lanes, deux balises : le split 3-2 ou 4-1 selon les matchups est la norme. Chaque pourcentage de balise compte (2 % toutes les 0,75 s) : rester sur la balise même à un contre un. Cycle : 130 s après la mort du dernier Zerg.
**Pièges** : les deux équipes à une balise chacun (égalité = pas de vague : négocier vite) ; ignorer la vague Zerg qui pousse (elle détruit vite un fort) ; envoyer 4 sur une balise pendant que l'adversaire la prend à 50 % sur l'autre.
**Héros qui marchent bien** : forts en 1v1 de balise (Yrel, Sonya, Artanis, Leoric), clear de Zerg (Kael'thas, Gul'dan, Junkrat, Xul), heals de soutien long (Lt. Morales, Ana, Lucio).
""",
    "warhead-junction": """# Menace nucléaire — Warhead Junction

**Objectif** : des ogives nucléaires apparaissent sur la carte ; les ramasser et les lancer (zone d'ombre = gros dégâts + zone irradiée) sur les structures ou les camps.
**Plan de jeu** : très grande carte = la mobilité est reine. Le lancement d'ogive se voit et s'interrompt : lancer depuis la sécurité ou en couverture. Après le lancement de la dernière ogive : 185 s avant le prochain spawn. Penser aux ogives non ramassées avant l'objectif suivant.
**Pièges** : mourir avec une ogive (elle tombe au sol et l'adversaire la prend) ; lancer en plein teamfight sans couverture (le channel s'interrompt) ; négliger les rotations (la carte est énorme, les morts coûtent cher).
**Héros qui marchent bien** : mobilité globale (Dehaka, Falstad, Brightwing), voleurs d'ogives (Zeratul, Tracer, Genji), duel et punition (Alarak, Kerrigan, Greymane).
""",
    "blackhearts-bay": """# La baie de Cœur-Noir — Blackheart's Bay

**Objectif** : collecter des doublons (coffres, camps de pirates) et les rapporter à Cœur-Noir (channel 5 s ; 8 doublons, +2 à chaque tour) = bombardement des structures ennemies.
**Plan de jeu** : carte de ressources : les camps de doublons et les comptent autant que les kills. Les coffres arrivent à 1:30 puis toutes les 3:00 (en pause pendant le bombardement). Mourir = jeter ses doublons : le turn-in se fait en sécurité, jamais dans un duel.
**Pièges** : accumuler 10+ doublons et mourir ; contester le turn-in adverse avec peu de doublons (le bombardement adverse est dévastateur) ; laisser les camps de doublons au camp adverse sans réaction.
**Héros qui marchent bien** : clear de camps et de coffres (Illidan, Sonya, Greymane, Kerrigan), voleurs de doublons (Zeratul, Tracer), pushers qui exploitent le bombardement (Sgt. Hammer, Azmodan, Zagara).
""",
    "haunted-mines": """# La mine hantée — Haunted Mines

**Objectif** : la mine s'ouvre (1re fois à 3:00) ; y collecter des crânes (100 par phase, 55 pour compléter) → chaque équipe reçoit un Golem d'Os dont la force dépend des crânes collectés ET du temps passé.
**Plan de jeu** : le split de collecte est rentable (72 crânes sur les mineurs, 38 sur le Golem de la mine). Qui finit à 55+ crânes domine la phase. La réouverture des mines est 2:00 après la mort des deux Golems — les Golems se défendent en lane pendant ce temps.
**Pièges** : rester sous terre pendant que le Golem adverse pousse la lane du haut ; ignorer le compteur de crânes (55 = seuil de complétion) ; se faire voler les paliers de crânes du Golem (8 crânes aux 75/50/25 %).
**Héros qui marchent bien** : clear de mine et de crânes (Johanna, Kael'thas, Gul'dan, Xul), défense de Golem (Sgt. Hammer, Hanzo), voleurs de crânes rapides (Tracer, Zeratul, Genji).
""",
    "silver-city": """# La cité d'argent — Silver City (ARAM)

**Objectif** : ARAM — une seule lane, pas d'objectif de carte. On se bat, on pousse, on finit.
**Plan de jeu** : le coaching se limite au micro, aux teamfights et à la gestion de la fontaine de soins. Composition aléatoire : s'adapter au pool donné.
**Pièges** : pas d'objectif sur lequel se reposer — chaque teamfight est la ressource principale.
**Héros qui marchent bien** : poke, sustain et clear de wave (c'est la méta ARAM).
""",
}


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    for slug, body in CARTES.items():
        path = os.path.join(OUT, f"{slug}.md")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(HEADER + "\n" + body)
    print(f"{len(CARTES)} fiches de carte écrites dans {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
