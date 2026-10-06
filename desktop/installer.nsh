# electron-builder includes this file for both installer and uninstaller builds.
# The AI page and its callbacks belong only to the installer; leaving them in
# BUILD_UNINSTALLER produces NSIS warning 6010 (fatal with warnings-as-errors).
!ifndef BUILD_UNINSTALLER
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "MUI2.nsh"
Var SFWhisper
Var SFImages
Var SFVoice
Var SFGpu
Var SFTerms
Var SFComponents
Var SFGpuFlag

!macro customPageAfterChangeDir
  Page custom SFLocalAIPage SFLocalAILeave
!macroend

Function SFLocalAIPage
  !insertmacro MUI_HEADER_TEXT "Set up local AI" "Choose optional tools to install with SceneForge."
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateLabel} 0 0 100% 20u "Install local AI with SceneForge. Downloads are shown in the installation log. Allow at least 15 GB of free space and internet access."
  Pop $0
  ${NSD_CreateCheckbox} 0 24u 100% 12u "Whisper - automatic captions (about 145 MB)"
  Pop $SFWhisper
  ${NSD_Check} $SFWhisper
  ${NSD_CreateCheckbox} 0 39u 100% 12u "Stable Diffusion - local pictures (several GB)"
  Pop $SFImages
  ${NSD_Check} $SFImages
  ${NSD_CreateCheckbox} 0 54u 100% 12u "Chatterbox - multilingual voices (several GB)"
  Pop $SFVoice
  ${NSD_Check} $SFVoice
  ${NSD_CreateCheckbox} 0 69u 100% 12u "Use NVIDIA GPU for images (requires driver and Docker GPU support)"
  Pop $SFGpu
  ${NSD_CreateLabel} 0 85u 100% 20u "Image and voice tools need Docker Desktop and may need a Windows restart. Review the component terms below."
  Pop $0
  ${NSD_CreateLink} 0 108u 30% 10u "Docker terms"
  Pop $0
  ${NSD_OnClick} $0 SFDockerTerms
  ${NSD_CreateLink} 33% 108u 30% 10u "Image model terms"
  Pop $0
  ${NSD_OnClick} $0 SFImageTerms
  ${NSD_CreateLink} 66% 108u 30% 10u "Voice model terms"
  Pop $0
  ${NSD_OnClick} $0 SFVoiceTerms
  ${NSD_CreateCheckbox} 0 124u 100% 12u "I accept the terms for the selected AI components."
  Pop $SFTerms
  nsDialogs::Show
FunctionEnd

Function SFDockerTerms
  Pop $0
  ExecShell "open" "https://www.docker.com/legal/docker-subscription-service-agreement/"
FunctionEnd
Function SFImageTerms
  Pop $0
  ExecShell "open" "https://huggingface.co/spaces/CompVis/stable-diffusion-license"
FunctionEnd
Function SFVoiceTerms
  Pop $0
  ExecShell "open" "https://github.com/resemble-ai/chatterbox/blob/master/LICENSE"
FunctionEnd

Function SFLocalAILeave
  StrCpy $SFComponents ""
  StrCpy $SFGpuFlag "0"
  ${NSD_GetState} $SFWhisper $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $SFComponents "whisper"
  ${EndIf}
  ${NSD_GetState} $SFImages $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $SFComponents "$SFComponents,stable_diffusion"
  ${EndIf}
  ${NSD_GetState} $SFVoice $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $SFComponents "$SFComponents,chatterbox"
  ${EndIf}
  ${NSD_GetState} $SFGpu $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $SFGpuFlag "1"
  ${EndIf}
  ${If} $SFComponents != ""
    ${NSD_GetState} $SFTerms $0
    ${If} $0 != ${BST_CHECKED}
      MessageBox MB_OK "Accept the terms for selected AI components, or uncheck them to install the editor only."
      Abort
    ${EndIf}
  ${EndIf}
FunctionEnd

!macro customInstall
  ${If} $SFComponents != ""
    DetailPrint "Installing selected local AI components. Large downloads can take many minutes."
    nsExec::ExecToLog '"$INSTDIR\resources\backend\sceneforge-backend.exe" --install-local-ai "$SFComponents" "$APPDATA\SceneForge Studio\workspace" "$SFGpuFlag"'
    Pop $0
    ${If} $0 != 0
      MessageBox MB_OK "SceneForge is installed. Local AI setup needs attention or a Windows restart. Open AI Engines - Set up free local AI to see progress and Retry."
    ${EndIf}
  ${EndIf}
!macroend
!endif # BUILD_UNINSTALLER
