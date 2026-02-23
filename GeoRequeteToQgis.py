import os
import shutil
import stat
import sys
from datetime import datetime


from pathlib import Path
import re

from PyQt5.QtWidgets import QApplication,QFileDialog
from mapping import *

FIC_LOG = "log.txt"

def log(message):
    """
    Écrit un message dans le fichier de log avec un horodatage.
    Le fichier est ouvert en mode append pour ne pas écraser les données.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(FIC_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


class GeoRequeteToQgis():
    def __init__(self):
        super().__init__()
        self.list_fic_requete = None

    def get_sous_dossier(self,rep_parent):
        for sous_dossier in os.scandir(rep_parent):
            if sous_dossier.is_dir():
                print("Sous-dossier :", sous_dossier.name)

    def get_fic_requete(self,rep_requete):
        self.list_fic_requete = [f for f in Path(rep_requete).iterdir() if f.is_file() and f.suffix == ".txt"]
        print(f"fichiers trouvés = {len(self.list_fic_requete)}")

    def convert_requete(self,dossier):
        for fic in self.list_fic_requete:
            print(fic)

            # test si le fichier est enregistré en unicode ou autre
            try:
                with open(fic, "r", encoding="utf-8") as f:
                    requete = f.read().strip()
            except UnicodeDecodeError:
                with open(fic, "r", encoding="latin-1") as f:
                    requete = f.read().strip()



            # Chercher une correspondance de type sous_type
            correspondance_type = None
            for type, sous_type in mapping_type_sstype.items():
                if type in requete:
                    correspondance_type = sous_type
                    break

            expr_qgis = requete

            # on remplace les decorations des VALEURS " par '
            # A FAIRE AVANT la recherche de correspondance de champ
            expr_qgis = expr_qgis.replace('"', "'")

            # Chercher une correspondance de champ
            for champGEO, champQGIS in mapping_champ.items():
                if champGEO in requete:
                    print("correspondance de champ trouvé :",champGEO,"-->",champQGIS)
                    expr_qgis = expr_qgis.replace(f"'{champGEO}'", f'"{champQGIS}"')



            # Transformation GeoConcept -> QGIS
            expr_qgis = expr_qgis.replace("= <No Value>", "IS NULL")
            expr_qgis = expr_qgis.replace("<>", "!=")  # != à la place de <>
            expr_qgis = expr_qgis.replace(" And ", " \nAND ")  # majuscule AND
            expr_qgis = expr_qgis.replace(" = ", " = ")  # juste pour clarté

            # Supprimer la partie Select From "Layer", ... si nécessaire
            # Ici on peut garder uniquement la condition après WHERE
            if "Where" in expr_qgis:
                expr_qgis = expr_qgis.split("Where", 1)[1].strip().rstrip(";")




            # chercher "Options(Select)"
            if "Options(Select)" in requete:
                print("ajout du mode SELECT")
                expr_qgis = "--MODE=SELECT\n" + expr_qgis
                expr_qgis = expr_qgis.replace("Options(Select)", "")

            # Ajouter correspondance en début
            if correspondance_type:
                expr_qgis = f"--LAYER={correspondance_type}\n{expr_qgis}"

            # Écrire dans un nouveau fichier dans le dossier output
            parent = Path(dossier).parent
            nouveau_dossier = "requetes_transformees"
            nouveau_dossier = parent / nouveau_dossier
            # Crée le dossier s'il n'existe pas déjà
            nouveau_dossier.mkdir(parents=True, exist_ok=True)

            nom_fic = Path(fic).name
            # print("fichier sortie = ",nom_fic)
            fichier_transforme = Path(nouveau_dossier) / nom_fic
            with open(fichier_transforme, "w",encoding="utf-8") as f_out:
                f_out.write(expr_qgis)

            # print(f"Fichier transformé : {fichier_transforme}")


    def convert_requete2(self,dossier):
        """
            Transforme une requête Geoconcept en dictionnaire QGIS:
            {
                'layer': nom_couche_qgis,
                'expression': expression_qgis
            }
            """
        for fic in self.list_fic_requete:
            print(fic)

            # test si le fichier est enregistré en unicode ou autre
            try:
                with open(fic, "r", encoding="utf-8") as f:
                    query = f.read().strip()
            except UnicodeDecodeError:
                with open(fic, "r", encoding="latin-1") as f:
                    query = f.read().strip()

            # 🔹 1️⃣ Détection de la couche
            couche_match = re.search(r'Select From\s*(.*?)\s*(?:Where|Options)', query, re.IGNORECASE)
            if not couche_match:
                raise ValueError("Impossible de trouver la clause FROM")
            couche_geoconcept = couche_match.group(1).strip()

            # mapping couche
            layer_qgis = mapping_type_sstype.get(couche_geoconcept)
            if not layer_qgis:
                raise ValueError(f"Aucun mapping QGIS trouvé pour la couche {couche_geoconcept}")

            # 🔹 2️⃣ Détection de la clause WHERE
            where_match = re.search(r'Where\s*\((.*?)\)\s*Options', query, re.IGNORECASE)
            expression_qgis = ""
            if where_match:
                conds = where_match.group(1).strip()
                print(conds)

                # 2a. Remplacement des champs via mapping_champ
                # for champ_gc, champ_qgis in mapping_champ.items():
                #     conds = re.sub(rf'"{re.escape(champ_gc)}"', f'"{champ_qgis}"', conds)
                # Chercher une correspondance de champ
                conds = conds.replace('"', "'")  # Remplace les guillemets par des apostrophes pour la recherche de champ
                for champGEO, champQGIS in mapping_champ.items():
                    if champGEO in query:
                        print("correspondance de champ trouvé :", champGEO, "-->", champQGIS)
                        conds = conds.replace(f"'{champGEO}'", f'"{champQGIS}"')
                print(conds)

                # 2b. Remplacement des valeurs spéciales
                conds = conds.replace('<"Source de restitution =">', 'IS NOT NULL')  # Exemple, à adapter
                # conds = conds.replace('<No Value>', 'IS NULL')

                # 2c. Remplacement des opérateurs spécifiques
                conds = conds.replace('And', '\nAND')
                conds = conds.replace('HasNot', 'NOT LIKE')
                conds = conds.replace('Has', 'LIKE')
                conds = conds.replace('<>', '!=')



                expression_qgis = conds

            # 🔹 3️⃣ Détection de Options(Select) pour mettre le mode
            if "Options(Select);" in query or "Options(Select)" in query:
                mode_qgis = "--MODE=SELECT\n"

            expression_qgis = f"{mode_qgis}\n{expression_qgis}"
            expression_qgis = f"--LAYER={layer_qgis}\n{expression_qgis}"

            # Écrire dans un nouveau fichier dans le dossier output
            parent = Path(dossier).parent
            nouveau_dossier = "requetes_transformees"
            nouveau_dossier = parent / nouveau_dossier
            # Crée le dossier s'il n'existe pas déjà
            nouveau_dossier.mkdir(parents=True, exist_ok=True)

            nom_fic = Path(fic).name
            # print("fichier sortie = ",nom_fic)
            fichier_transforme = Path(nouveau_dossier) / nom_fic
            with open(fichier_transforme, "w", encoding="utf-8") as f_out:
                f_out.write(expression_qgis)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    geo = GeoRequeteToQgis()

    dossier = QFileDialog.getExistingDirectory(None, "Sélectionner un dossier")
    if dossier:
        print(f"Dossier choisi : {dossier}")
        geo.get_fic_requete(dossier)
        # geo.convert_requete(dossier)
        geo.convert_requete2(dossier)




