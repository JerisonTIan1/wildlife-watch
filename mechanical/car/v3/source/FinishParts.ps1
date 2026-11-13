$ErrorActionPreference='Stop'
$interop='C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\api\redist\SolidWorks.Interop.sldworks.dll'
Add-Type -Path $interop
Add-Type -ReferencedAssemblies @($interop,'System.Collections.dll','System.Console.dll','System.Runtime.dll','System.Runtime.InteropServices.dll','System.IO.FileSystem.dll') -Path "$PSScriptRoot\FinishParts.cs"
[FinishParts]::Run((Split-Path $PSScriptRoot -Parent))
