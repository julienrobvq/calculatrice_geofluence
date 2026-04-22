from qgis.core import (
    QgsProject, 
    QgsExpression, 
    QgsExpressionContext, 
    QgsExpressionContextUtils, 
    QgsFeature 
)
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QMessageBox, QAction, QToolBar, QCheckBox, QLabel
)
from qgis.utils import iface

from PyQt5.QtCore import Qt

class CalculatriceGeofluence:
    def __init__(self, iface):
        self.iface = iface
        self.window = iface.mainWindow()
        self.toolbar = [
            c for c in self.window.children()
            if isinstance(c, QToolBar) and c.objectName() == 'mPluginToolBar'
        ][0]
        self.action = QAction("Calculatrice Géofluence", self.window)

    def initGui(self):
        self.action.setObjectName('btnGo')
        self.toolbar.addAction(self.action)
        self.action.triggered.connect(self.run)
        iface.addPluginToMenu("&Calculatrice Géofluence", self.action)
        iface.addToolBarIcon(self.action)

    def run(self):
        # liste des formulaire
        layers = [
            layer for layer in QgsProject.instance().mapLayers().values()
            if layer.id().startswith("form")
        ]
        
        if not layers:
            QMessageBox.warning(None, "Calculatrice Géofluence", "Aucun formulaire Géofluence trouvé.")
            return

        # sélection du formulaire
        layer_dialog = LayerSelectionDialog(layers)
        if layer_dialog.exec_() != QDialog.Accepted:
            return
        
        selected_layer_names = layer_dialog.get_selected_layers()
        if not selected_layer_names:
            QMessageBox.warning(None, "Calculatrice Géofluence", "Aucune couche sélectionnée.")
            return

        layer = next(l for l in layers if l.name() in selected_layer_names)

        
        self.process_layer(layer)


    def process_layer(self, layer):
        if not layer.isEditable():
            layer.startEditing()

        # liste champ qui répondent aux criteres (val par défaut appliquée sur maj)
        eligible_fields = []
        for field in layer.fields():
            i = layer.fields().indexOf(field.name())
            def_val_def = layer.fields().field(i).defaultValueDefinition()

            if not def_val_def:
                continue
            if not def_val_def.expression():
                continue
            if not def_val_def.applyOnUpdate():
                continue

            eligible_fields.append(field.name())

        if not eligible_fields:
            QMessageBox.information(
                None,
                "Calculatrice Géofluence",
                f"Aucun champ applicable dans {layer.name()}."
            )
            return

        recalculated_fields = set()

        for feature in layer.getFeatures():
            new_feature = QgsFeature(feature) 

            for field_name in eligible_fields:
                idx = layer.fields().indexOf(field_name)
                def_val_def = layer.fields().field(idx).defaultValueDefinition()
                expr = def_val_def.expression()
                if not expr:
                    continue

                exp = QgsExpression(expr)

                context = QgsExpressionContext()
                context.setFeature(feature)
                context.appendScope(QgsExpressionContextUtils.layerScope(layer))
                context.appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))

                value = exp.evaluate(context)
                if exp.hasEvalError():
                    print(f"[ERREUR] {field_name} : {exp.evalErrorString()}")
                    continue

                new_feature[field_name] = value
                recalculated_fields.add(field_name)
                print(f"[OK] {field_name} = {value}")

            layer.updateFeature(new_feature)

        if recalculated_fields:
            fields_list = "\n  - " + "\n  - ".join(sorted(recalculated_fields))
        else:
            fields_list = "\n  (Aucun champ recalculé)"

        QMessageBox.information(
            None,
            "Calculatrice Géofluence",
            f"Recalcul terminé pour : {layer.name()}\n\n"
            f"Champs recalculés :{fields_list}\n\n"
            f"Les modifications ne sont pas enregistrées automatiquement.\n\n"
            f"Vous devez valider la mise à jour manuellement."
        )

    def unload(self):
        self.toolbar.removeAction(self.action)
        iface.removePluginMenu("&Calculatrice Géofluence", self.action)
        iface.removeToolBarIcon(self.action)
        del self.action


class LayerSelectionDialog(QDialog):
    def __init__(self, layers):
        super().__init__()
        self.setWindowTitle("Sélectionner une couche")
        self.setFixedWidth(400)
        self.layout = QVBoxLayout(self)

        self.checkboxes = []

        for layer in layers:
            cb = QCheckBox(layer.name(), self)
            cb.stateChanged.connect(self.on_state_changed)
            self.layout.addWidget(cb)
            self.checkboxes.append(cb)
        
        self.button = QPushButton("OK", self)
        self.button.clicked.connect(self.accept)
        self.layout.addWidget(self.button)

    def on_state_changed(self, state):
        if state == Qt.Checked:
            for cb in self.checkboxes:
                if cb != self.sender():
                    cb.setChecked(False)

    def get_selected_layers(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]