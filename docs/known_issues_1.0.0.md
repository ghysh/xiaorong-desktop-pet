# Desktop Pet 1.0.0 known issues

- Transparent pixels are Alpha-aware for click feedback but still occupy the rectangular Qt window and block lower-window mouse input.
- The application is unsigned, so Windows or security software may show an unverified-publisher warning.
- There is no automatic movement, walking, jumping, blinking, expression-frame system, dialogue, sound, startup registration, or automatic update.
- A separate-instance guard is not included in 1.0.0. Starting the executable twice can create two pets and two tray icons; users should run one instance at a time. A rushed inter-process notification mechanism was deliberately excluded from the frozen release scope.
- Real tray appearance, topmost behavior across arbitrary third-party applications, and multi-monitor DPI transitions remain dependent on the Windows desktop environment.
- The recommended artifact is the onedir portable ZIP. A onefile build is optional and is not required for acceptance.
- Independent Windows Sandbox validation must be reported separately; it must not be inferred from local extraction testing.
