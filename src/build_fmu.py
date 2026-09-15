"""Build a native FMI 2.0 controller and package its source alongside the FMU."""
from pathlib import Path
import json,subprocess,zipfile,xml.etree.ElementTree as ET
from config import ROOT,OUT
HERE=Path(__file__).parent/'fmu';HERE.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
if not (HERE/'fmi2_minimal.h').exists():raise FileNotFoundError('The FMI header must remain alongside its source and license notices')
inputs=['presence','objectId','defectScore','washed','boxCount','boxReady','armBusy','palletCount','targetCount']
outputs=['acceptPulse','rejectPulse','decisionId','valvePressure','conveyorRun','packRequest','forkliftRequest','acceptedTotal','rejectedTotal']
variables=[(n,i,'input',18. if n=='targetCount' else 0.) for i,n in enumerate(inputs)]+[(n,20+i,'output',None) for i,n in enumerate(outputs)]+[('defectThreshold',50,'parameter',.10),('boxTarget',51,'parameter',18.)]
# FactoryController.cpp is the editable source of truth. Rebuilding must
# preserve user changes to its inspection and actuator logic.
root=ET.Element('fmiModelDescription',fmiVersion='2.0',modelName='FactoryController',guid='{c16c2a15-675c-4bba-a66c-76e48dcb7a6f}',generationTool='FIELD / FLOW native FMI build',description='Quality sensor, pneumatic valve and packaging interlocks')
ET.SubElement(root,'CoSimulation',modelIdentifier='FactoryController',canHandleVariableCommunicationStepSize='true')
ET.SubElement(root,'DefaultExperiment',startTime='0',stepSize='0.03333333333333333')
vs=ET.SubElement(root,'ModelVariables');out_indices=[]
for index,(name,vr,causality,start) in enumerate(variables,1):
 kw=dict(name=name,valueReference=str(vr),causality=causality,variability='fixed' if causality=='parameter' else 'continuous')
 if causality=='output':kw['initial']='calculated';out_indices.append(index)
 var=ET.SubElement(vs,'ScalarVariable',kw);ET.SubElement(var,'Real',{} if start is None else {'start':str(start)})
ms=ET.SubElement(root,'ModelStructure');outputs_xml=ET.SubElement(ms,'Outputs')
for i in out_indices:ET.SubElement(outputs_xml,'Unknown',index=str(i))
initial_xml=ET.SubElement(ms,'InitialUnknowns')
for i in out_indices:ET.SubElement(initial_xml,'Unknown',index=str(i))
ET.indent(root);ET.ElementTree(root).write(HERE/'modelDescription.xml',encoding='utf-8',xml_declaration=True)
build=HERE/'build.cmd'
build.write_text('@echo off\ncall "C:\\Program Files (x86)\\Microsoft Visual Studio\\2022\\BuildTools\\VC\\Auxiliary\\Build\\vcvars64.bat"\ncd /d "%~dp0"\ncl /nologo /LD /O2 /MT /EHsc FactoryController.cpp /link /OUT:FactoryController.dll\n')
subprocess.run(['cmd','/c',str(build)],check=True,cwd=HERE)
with zipfile.ZipFile(OUT/'FactoryController.fmu','w',zipfile.ZIP_DEFLATED) as z:
 z.write(HERE/'modelDescription.xml','modelDescription.xml');z.write(HERE/'FactoryController.dll','binaries/win64/FactoryController.dll')
 for f in ['FactoryController.cpp','fmi2_minimal.h']:z.write(HERE/f,'sources/'+f)
 z.write(ROOT/'LICENSE','documentation/ovfmi-LICENSE')
(OUT/'fmu_variables.json').write_text(json.dumps({'inputs':inputs,'outputs':outputs,'variables':variables},indent=2))
from fmpy.validation import validate_fmu
problems=validate_fmu(str(OUT/'FactoryController.fmu'));print('FMU_VALIDATION',problems)
if problems:raise SystemExit(1)
print('FMU_BUILT',flush=True)
