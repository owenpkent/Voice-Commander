import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Controls.Material 2.15

ApplicationWindow {
    id: win
    width: 800
    height: 600
    visible: true
    title: "Whisper Transcriber"

    Material.theme: Material.Dark
    Material.accent: Material.Teal

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // Top options row
        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            Label { text: "Backend:" }
            ComboBox {
                id: backendCombo
                Layout.preferredWidth: 120
                model: ["API", "Local"]
                currentIndex: model.indexOf(controller.backend)
                onCurrentIndexChanged: controller.backend = model[currentIndex]
            }

            Label { text: "Local model:" }
            ComboBox {
                id: modelCombo
                Layout.preferredWidth: 160
                model: ["tiny.en", "base.en", "small.en", "medium.en", "large-v3"]
                currentIndex: model.indexOf(controller.localModel)
                onCurrentIndexChanged: controller.localModel = model[currentIndex]
            }

            Item { Layout.fillWidth: true }
        }

        // Command Mode toggle and last command
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Label { text: "Command Mode" }
            Switch {
                id: cmdSwitch
                checked: controller.commandMode
                onToggled: controller.commandMode = checked
            }

            CheckBox {
                id: requireWake
                text: "Require 'Command' wake word"
                checked: controller.requireWakeWord
                onToggled: controller.requireWakeWord = checked
            }

            Label {
                Layout.fillWidth: true
                text: controller.lastCommand && controller.lastCommand.length > 0 ?
                        ("Last: " + controller.lastCommand) : "Last: —"
                color: "#bbb"
                elide: Text.ElideRight
            }
        }

        // Level meter with mic icon
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Label {
                text: "🎤"
                font.pixelSize: 18
                verticalAlignment: Text.AlignVCenter
            }

            Rectangle {
                Layout.fillWidth: true
                height: 20
                radius: 10
                color: "#333"
                border.color: "#444"
                border.width: 1

                Rectangle {
                    id: levelBar
                    anchors.verticalCenter: parent.verticalCenter
                    height: parent.height - 4
                    x: 2
                    width: (parent.width - 4) * Math.max(0, Math.min(1, controller.level))
                    radius: 8
                    color: controller.level < 0.6 ? "#3FBF9E" : (controller.level < 0.85 ? "#E6A23C" : "#E65C5C")
                }
            }
        }

        // Controls
        RowLayout {
            spacing: 8
            Layout.fillWidth: true

            Button {
                text: "● Record"
                enabled: !controller.recording
                onClicked: controller.startRecording()
            }
            Button {
                text: "■ Stop"
                enabled: controller.recording
                onClicked: controller.stopRecording()
            }
            Button {
                text: "Transcribe"
                onClicked: controller.transcribe()
            }
            Button {
                text: "Copy Text"
                onClicked: controller.copyText()
            }
            Item { Layout.fillWidth: true }
        }

        // Status
        Label {
            text: controller.status
            color: "#bbb"
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        // Debug log controls
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            CheckBox {
                id: showLog
                text: "Show Debug Log"
                checked: false
            }
            Button {
                text: "Clear Log"
                onClicked: controller.clearLog()
            }
            Item { Layout.fillWidth: true }
        }

        // Debug log view
        Rectangle {
            visible: showLog.checked
            Layout.fillWidth: true
            Layout.preferredHeight: 160
            radius: 6
            color: "#222"
            border.color: "#444"
            border.width: 1

            ScrollView {
                anchors.fill: parent
                clip: true
                TextArea {
                    id: logArea
                    anchors.fill: parent
                    readOnly: true
                    wrapMode: Text.NoWrap
                    text: controller.logText
                    font.family: "Consolas"
                    font.pixelSize: 12
                    onTextChanged: {
                        cursorPosition = text.length
                        if (flickableItem) {
                            flickableItem.contentY = flickableItem.contentHeight
                        }
                    }
                }
            }
        }

        // Transcript
        TextArea {
            Layout.fillWidth: true
            Layout.fillHeight: true
            wrapMode: Text.Wrap
            text: controller.transcript
            readOnly: false
            placeholderText: "Transcription will appear here..."
        }
    }
}
