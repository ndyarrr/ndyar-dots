import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import Quickshell.Services.SystemTray

Item {
    id: root

    property var targetItem: null
    property var menuHandle: null
    property var mocha: null
    property var barWindow: null
    property real baseScale: 1.0

    function s(v) {
        if (barWindow && typeof barWindow.s === "function") {
            return barWindow.s(v);
        }
        return Math.round(v * baseScale);
    }

    PopupWindow {
        id: popupWin
        anchor.window: root.barWindow
        anchor.item: root.targetItem

        anchor.edges: {
            let pos = root.barWindow ? root.barWindow.topbarPosition : "top";
            if (pos === "bottom") return Edges.Top | Edges.Left;
            if (pos === "left") return Edges.Right | Edges.Top;
            if (pos === "right") return Edges.Left | Edges.Top;
            return Edges.Bottom | Edges.Left;
        }

        anchor.gravity: {
            let pos = root.barWindow ? root.barWindow.topbarPosition : "top";
            if (pos === "bottom") return Edges.Top | Edges.Right;
            if (pos === "left") return Edges.Right | Edges.Bottom;
            if (pos === "right") return Edges.Left | Edges.Bottom;
            return Edges.Bottom | Edges.Right;
        }

        // Explicit dimensions so Wayland surface does not clip
        implicitWidth: menuCard.width
        implicitHeight: menuCard.height
        width: menuCard.width
        height: menuCard.height

        grabFocus: true
        color: "transparent"
        visible: false

        QsMenuOpener {
            id: menuOpener
            menu: popupWin.visible ? root.menuHandle : null
        }

        Rectangle {
            id: menuCard
            width: root.s(220)
            height: contentCol.implicitHeight + root.s(16)
            radius: root.s(12)

            color: root.mocha ? Qt.rgba(root.mocha.mantle.r, root.mocha.mantle.g, root.mocha.mantle.b, 0.96) : "#181825ee"
            border.width: 1
            border.color: root.mocha ? Qt.rgba(root.mocha.text.r, root.mocha.text.g, root.mocha.text.b, 0.14) : "#45475a"
            clip: true

            Column {
                id: contentCol
                anchors.top: parent.top
                anchors.topMargin: root.s(8)
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width - root.s(16)
                spacing: root.s(2)

                Repeater {
                    model: (popupWin.visible && menuOpener.children) ? menuOpener.children : null
                    delegate: Item {
                        id: entryDelegate
                        required property var modelData

                        width: parent.width
                        height: (modelData && modelData.isSeparator) ? root.s(8) : root.s(32)

                        // Separator Line
                        Rectangle {
                            visible: Boolean(modelData && modelData.isSeparator)
                            anchors.centerIn: parent
                            width: parent.width - root.s(4)
                            height: 1
                            color: root.mocha ? Qt.rgba(root.mocha.surface1.r, root.mocha.surface1.g, root.mocha.surface1.b, 0.6) : "#45475a"
                        }

                        // Menu Item Button
                        Rectangle {
                            id: itemButton
                            visible: Boolean(modelData && !modelData.isSeparator)
                            anchors.fill: parent
                            radius: root.s(8)
                            color: (entryMouse.containsMouse && modelData && modelData.enabled !== false)
                                ? (root.mocha ? Qt.rgba(root.mocha.surface1.r, root.mocha.surface1.g, root.mocha.surface1.b, 0.8) : "#45475a")
                                : "transparent"
                            opacity: (modelData && modelData.enabled !== false) ? 1.0 : 0.4

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: root.s(8)
                                anchors.rightMargin: root.s(8)
                                spacing: root.s(8)

                                // Check / Radio / Icon indicator
                                Item {
                                    Layout.preferredWidth: root.s(16)
                                    Layout.preferredHeight: root.s(16)
                                    Layout.alignment: Qt.AlignVCenter

                                    Text {
                                        anchors.centerIn: parent
                                        visible: Boolean(modelData && modelData.buttonType !== undefined && modelData.buttonType !== 0 && (modelData.checkState === Qt.Checked || modelData.checked))
                                        text: (modelData && modelData.buttonType === 2) ? "" : ""
                                        font.family: "Iosevka Nerd Font"
                                        font.pixelSize: root.s(11)
                                        color: root.mocha ? root.mocha.mauve : "#cba6f7"
                                    }

                                    Image {
                                        anchors.centerIn: parent
                                        visible: (!parent.children[0].visible) && Boolean(modelData && modelData.icon)
                                        source: (modelData && modelData.icon) ? modelData.icon : ""
                                        width: root.s(14)
                                        height: root.s(14)
                                        fillMode: Image.PreserveAspectFit
                                    }
                                }

                                // Text Label
                                Text {
                                    Layout.fillWidth: true
                                    Layout.alignment: Qt.AlignVCenter
                                    text: (modelData && (modelData.text || modelData.label)) ? (modelData.text || modelData.label).replace(/&/g, "") : ""
                                    font.family: "JetBrains Mono"
                                    font.pixelSize: root.s(12)
                                    font.weight: entryMouse.containsMouse ? Font.DemiBold : Font.Normal
                                    color: entryMouse.containsMouse
                                        ? (root.mocha ? root.mocha.mauve : "#cba6f7")
                                        : (root.mocha ? root.mocha.text : "#cdd6f4")
                                    elide: Text.ElideRight
                                }

                                // Submenu indicator
                                Text {
                                    visible: Boolean(modelData && modelData.hasChildren)
                                    Layout.alignment: Qt.AlignVCenter
                                    text: ""
                                    font.family: "Iosevka Nerd Font"
                                    font.pixelSize: root.s(10)
                                    color: root.mocha ? root.mocha.subtext0 : "#a6adc8"
                                }
                            }

                            MouseArea {
                                id: entryMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: (modelData && modelData.enabled !== false) ? Qt.PointingHandCursor : Qt.ArrowCursor
                                onClicked: {
                                    if (!modelData || modelData.enabled === false) return;
                                    if (typeof modelData.activate === "function") {
                                        modelData.activate();
                                    }
                                    popupWin.visible = false;
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    function show(item, menu) {
        root.targetItem = item;
        root.menuHandle = menu;
        popupWin.visible = true;
    }

    function hide() {
        popupWin.visible = false;
    }

    function toggle(item, menu) {
        if (popupWin.visible && root.targetItem === item) {
            hide();
        } else {
            show(item, menu);
        }
    }
}
