# electron-builder includes this file for both installer and uninstaller builds.
# The AI page and its callbacks belong only to the installer; leaving them in
# BUILD_UNINSTALLER produces NSIS warning 6010 (fatal with warnings-as-errors).
!ifndef BUILD_UNINSTALLER
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "MUI2.nsh"
Var SFWhisper
Var SFKokoro
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
  !insertmacro MUI_HEADER_TEXT "Set up local AI" "Choose optional tools. SceneForge sets them up after it opens."
  nsDialogs::Create 1018
  Pop $0
  ${NSD_CreateLabel} 0 0 100% 18u "Free AI that runs on this computer. Installing SceneForge stays quick: the selected tools download when SceneForge first opens, with progress shown there. No Docker needed."
  Pop $0
  ${NSD_CreateCheckbox} 0 21u 100% 12u "Whisper - automatic captions (about 145 MB)"
  Pop $SFWhisper
  ${NSD_Check} $SFWhisper
  ${NSD_CreateCheckbox} 0 34u 100% 12u "Kokoro - built-in narration voices (about 120 MB)"
  Pop $SFKokoro
  ${NSD_Check} $SFKokoro
  ${NSD_CreateCheckbox} 0 47u 100% 12u "Stable Diffusion - local pictures (about 6 GB)"
  Pop $SFImages
  ${NSD_CreateCheckbox} 0 60u 100% 12u "Chatterbox - Arabic and multilingual voices (about 3 GB)"
  Pop $SFVoice
  ${NSD_CreateCheckbox} 0 73u 100% 12u "Use my NVIDIA graphics card for pictures and voices"
  Pop $SFGpu
  ${NSD_CreateLabel} 0 88u 100% 18u "Allow about 12 GB of free space for everything. You can add or remove tools later in AI Engines. Review the component terms below."
  Pop $0
  ${NSD_CreateLink} 0 109u 45% 10u "Image model terms"
  Pop $0
  ${NSD_OnClick} $0 SFImageTerms
  ${NSD_CreateLink} 50% 109u 45% 10u "Voice model terms"
  Pop $0
  ${NSD_OnClick} $0 SFVoiceTerms
  ${NSD_CreateCheckbox} 0 124u 100% 12u "I accept the terms for the selected AI components."
  Pop $SFTerms
  nsDialogs::Show
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
  ${NSD_GetState} $SFKokoro $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $SFComponents "$SFComponents,kokoro"
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
    DetailPrint "The selected local AI tools will download when SceneForge first opens."
    nsExec::ExecToLog '"$INSTDIR\resources\backend\sceneforge-backend.exe" --queue-local-ai "$SFComponents" "$APPDATA\SceneForge Studio\workspace" "$SFGpuFlag"'
    Pop $0
  ${EndIf}
!macroend
!endif # BUILD_UNINSTALLER
