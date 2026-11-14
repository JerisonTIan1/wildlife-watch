using System;
using System.IO;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using SolidWorks.Interop.sldworks;

// All design coordinates below are millimetres; SOLIDWORKS API uses metres.
// Reference envelopes are NOT identification of the user's actual parts.
public sealed class BuildCar {
 ISldWorks sw; IModelDoc2 m; string root, template; bool resume;
 List<string> report = new List<string>();
 Dictionary<string,string> paths = new Dictionary<string,string>();
 const double L=220, W=130, H=40, T=2.4, AxleX=70, AxleZ=13.5;
 static double M(double mm) { return mm/1000.0; }
 bool Existing(string name) {
  string p=Path.Combine(root,"parts",name+"_V3.SLDPRT");
  if(!resume || !File.Exists(p))return false;
  int e=0,w=0;IModelDoc2 loaded=sw.OpenDoc6(p,1,1,"",ref e,ref w);
  if(loaded==null)throw new Exception("Cannot reopen "+p+" "+e);
  paths[name]=p;Say("Reused "+name);return true;
 }
 void Say(string text) { Console.WriteLine(text); Console.Out.Flush(); }
 void New(string name) {
  m=(IModelDoc2)sw.NewDocument(template,0,0,0);
  if(m==null)throw new Exception("NewDocument failed: "+name);
  m.SetTitle2(name+"_V3"); paths[name]=Path.Combine(root,"parts",name+"_V3.SLDPRT");
  m.SetUserPreferenceIntegerValue(263,5); // MMGS document display
 }
 void Sketch() {
  m.ClearSelection2(true);
  if(!m.Extension.SelectByID2("Front Plane","PLANE",0,0,0,false,0,null,0))
   throw new Exception("Front plane selection failed");
  m.SketchManager.InsertSketch(true);
 }
 void Rect(double x1,double y1,double x2,double y2) {
  m.SketchManager.CreateCornerRectangle(M(x1),M(y1),0,M(x2),M(y2),0);
 }
 void Poly(double[,] pts) {
  int n=pts.GetLength(0);
  for(int i=0;i<n;i++) {int j=(i+1)%n;
   if(m.SketchManager.CreateLine(M(pts[i,0]),M(pts[i,1]),0,M(pts[j,0]),M(pts[j,1]),0)==null)throw new Exception("Polygon segment failed");
  }
 }
 void Octagon(double x1,double y1,double x2,double y2,double c) {
  Poly(new double[,]{{x1+c,y1},{x2-c,y1},{x2,y1+c},{x2,y2-c},{x2-c,y2},{x1+c,y2},{x1,y2-c},{x1,y1+c}});
 }
 void RoofPod() {
  if(Existing("Sloped_Webcam_Roof"))return;
  New("Sloped_Webcam_Roof");Sketch();Octagon(-90,-50,70,50,12);m.SketchManager.InsertSketch(true);
  Feature f=m.FeatureManager.FeatureExtrusion2(true,false,false,0,0,M(6),0,true,false,false,false,Math.PI/4,0,false,false,false,false,true,true,true,3,0,false);
  if(f==null)throw new Exception("Roof draft failed");f.Name="Sloped_45deg_Roof_Flat_Webcam_Top";
  Save("Sloped_Webcam_Roof",true,0.12,0.16,0.20);
 }
 void ArchTrim() {
  if(Existing("Wheel_Arch_Trim"))return;
  New("Wheel_Arch_Trim");Sketch();Circle(0,0,30);Finish("Arch_Outer",0,3);
  Hole("Wheel_Clearance_R27",0,0,27,-0.1,3.2);
  Box("Open_Bottom_At_Ground_Clearance",-31,-31,31,-10.5,-0.1,3.2,true);
  Save("Wheel_Arch_Trim",true,0.10,0.13,0.16);
 }
 void Circle(double x,double y,double r) {
  if(m.SketchManager.CreateCircleByRadius(M(x),M(y),0,M(r))==null)
   throw new Exception("Circle failed");
 }
 void Finish(string name,double z,double depth,bool cut=false) {
  m.SketchManager.InsertSketch(true);
  Feature f;
  if(cut) f=m.FeatureManager.FeatureCut3(true,false,true,0,0,M(depth),0,false,false,false,false,0,0,false,false,false,false,false,true,true,false,false,false,3,M(z),false);
  else f=m.FeatureManager.FeatureExtrusion2(true,false,false,0,0,M(depth),0,false,false,false,false,0,0,false,false,false,false,true,true,true,3,M(z),false);
  if(f==null)throw new Exception("Feature failed: "+name);
  f.Name=name;
  bool warning=false; int code=f.GetErrorCode2(out warning);
  if(code!=0 && !warning)throw new Exception("Feature error "+name+": "+code);
 }
 void Box(string name,double x1,double y1,double x2,double y2,double z,double depth,bool cut=false) {
  Sketch(); Rect(x1,y1,x2,y2); Finish(name,z,depth,cut);
 }
 void Hole(string name,double x,double y,double radius,double z,double depth) {
  Sketch(); Circle(x,y,radius); Finish(name,z,depth,true);
 }
 void Color(double r,double g,double b) { m.MaterialPropertyValues=new double[]{r,g,b,0.9,0.7,0.15,0.2,0,0}; }
 void Save(string name,bool printable,double r,double g,double b) {
  m.ForceRebuild3(false);Color(r,g,b);m.ShowNamedView2("*Isometric",7);m.ViewZoomtofit2();
  object[] bodies=(object[])((IPartDoc)m).GetBodies2(0,false);
  if(bodies==null || bodies.Length!=1)throw new Exception(name+" expected one solid");
  int bodyCheck=((IBody2)bodies[0]).Check2();
  if(bodyCheck!=0)throw new Exception(name+" body check="+bodyCheck);
  double[] box=(double[])((IPartDoc)m).GetPartBox(true);
  double[] mass=(double[])((IBody2)bodies[0]).GetMassProperties(1);
  string bounds=String.Format(System.Globalization.CultureInfo.InvariantCulture,"{0:F3},{1:F3},{2:F3}",(box[3]-box[0])*1000,(box[4]-box[1])*1000,(box[5]-box[2])*1000);
  report.Add(name+","+(printable?"PRINT":"REFERENCE")+","+bounds+","+(mass[3]*1e9).ToString("F3",System.Globalization.CultureInfo.InvariantCulture)+",1,0");
  int e=0,w=0;
  if(!m.Extension.SaveAs(paths[name],0,1,null,ref e,ref w)||e!=0)throw new Exception("Save failed "+name+" "+e);
  if(printable) {
   string stl=Path.Combine(root,"stl_fit_check",name+".stl");
   if(!m.Extension.SaveAs(stl,0,1,null,ref e,ref w)||e!=0)throw new Exception("STL failed "+name+" "+e);
  }
  Say("Created "+name+"; bounds_mm="+bounds);
 }
 void Chassis() {
  if(Existing("Chassis_FWD"))return;
  New("Chassis_FWD");
  Sketch();Octagon(-110,-65,110,65,8);Finish("Faceted_Floor_220x130",0,T);
  Sketch();Octagon(-110,-65,110,65,8);Octagon(-107.6,-62.6,107.6,62.6,6.59411255);Finish("Faceted_Hollow_Walls_2p4",T,H-T);
  // Lid screw posts: attached to adjacent walls, with printable M3 pilot holes.
  foreach(int sx in new[]{-1,1})foreach(int sy in new[]{-1,1}) {
   double x=sx*102,y=sy*57;
   Box("Lid_Post_"+sx+"_"+sy,x-5.6,y-5.6,x+5.6,y+5.6,T,H-T);
   Hole("M3_Pilot_"+sx+"_"+sy,x,y,1.3,27,14);
  }
  // 130-size reference: 27.5 axial x 20 wide x 15 high; floor at Z=6.
  foreach(int side in new[]{-1,1}) {
   double ya=side>0?35:-65,yb=side>0?65:-35;
   Box("Motor_Saddle_Base_"+side,55,ya,85,yb,T,6-T);
   Box("Motor_Guide_A_"+side,55,ya,59.7,yb,6,12);
   Box("Motor_Guide_B_"+side,80.3,ya,85,yb,6,12);
   foreach(double y0 in new[]{43.0,55.0})foreach(double x0 in new[]{56.0,81.0})
    Box("TieSlot_"+side+"_"+x0+"_"+y0,x0,side>0?y0:-y0-4,x0+3,side>0?y0+4:-y0,-0.1,19,true);
   // Clearance for body/shaft at side walls; do not obstruct motor terminals.
   Box("Motor_Side_Window_"+side,58,side>0?62.5:-66,82,side>0?66:-62.5,4,22,true);
   // Continuous printed rear axle, shifted rearward to clear the breadboard.
   Box("Rear_Axle_Support_"+side,-103,side>0?55:-65,-87,side>0?65:-55,T,23-T);
   Box("Rear_Printed_Axle_Clearance_8p6"+side,-99.3,side>0?51:-66,-90.7,side>0?66:-51,9.2,8.6,true);
  }
  // Openings are generous cable/optical access, not connector snap-fit holes.
  Box("Rear_USB_Access_24x22",-111,-12,-107.5,12,8,22,true);
  Box("Front_ToF_Window_32x20",107.5,-16,111,16,12,20,true);
  foreach(int sy in new[]{-1,1})
   Box("ToF_M3_Clearance_"+sy,107.5,sy*22-1.7,111,sy*22+1.7,20.3,3.4,true);
  // Shallow locators leave an unobstructed 180 x 60 electronics footprint.
  Box("Breadboard_Left_Guide",-92,-33,92,-31,T,2);
  Box("Breadboard_Right_Guide",-92,31,92,33,T,2);
  // Trim post corners to the chamfered exterior without moving the screw centers.
  foreach(int sx in new[]{-1,1})foreach(int sy in new[]{-1,1}) {
   Sketch();Poly(new double[,]{{sx*102,sy*65},{sx*110,sy*57},{sx*110,sy*65}});Finish("Outer_Corner_Trim_"+sx+"_"+sy,-0.1,40.2,true);
  }
  Sketch();Poly(new double[,]{{108,-60},{114,-54},{118,-38},{118,38},{114,54},{108,60}});Finish("Angled_Front_Bumper",2.4,5.1);
  Sketch();Poly(new double[,]{{-108,-45},{-112,-45},{-116,-39},{-116,39},{-112,45},{-108,45}});Finish("Angled_Rear_Bumper",2.4,5.1);
  Save("Chassis_FWD",true,0.22,0.56,0.68);
 }
 void Lid() {
  if(Existing("Flat_Webcam_Lid"))return;
  New("Flat_Webcam_Lid");
  Sketch();Octagon(-110,-65,110,65,8);Finish("Faceted_Removable_Lid",0,2);
  // Model printed face-down, with locating tabs pointing up; assembly flips it.
  foreach(int s in new[]{-1,1}) {
   Box("Side_Locator_"+s,-10,s>0?60.3:-62.3,10,s>0?62.3:-60.3,2,3);
   Box("End_Locator_"+s,s>0?105.3:-107.3,-10,s>0?107.3:-105.3,10,2,3);
  }
  foreach(int sx in new[]{-1,1})foreach(int sy in new[]{-1,1})Hole("M3_Lid_Clearance_"+sx+"_"+sy,sx*102,sy*57,1.7,-0.1,2.2);
  Save("Flat_Webcam_Lid",true,0.22,0.56,0.68);
 }
 void Wheel(string name,double bore) {
  if(Existing(name))return;
  New(name);Sketch();Circle(0,0,25);Finish("Wheel_Web_50mm",0,2.2);
  Sketch();Circle(0,0,25);Circle(0,0,22.5);Finish("Outer_Rim_10mm_Wide",2.2,7.8);
  Sketch();Circle(0,0,6);Finish("Hub_12mm",2.2,7.8);
  Hole("Axle_Bore_FIT_CHECK",0,0,bore/2,-0.1,10.2);
  foreach(double x in new[]{-13.5,13.5})Hole("Lightening_X_"+x,x,0,5,-0.1,10.2);
  foreach(double y in new[]{-13.5,13.5})Hole("Lightening_Y_"+y,0,y,5,-0.1,10.2);
  Save(name,true,0.1,0.1,0.12);
 }
 void Ring(string name,double outer,double inner,double length,bool printable) {
  if(Existing(name))return;
  New(name);Sketch();Circle(0,0,outer/2);Finish("Sleeve_Outer",0,length);
  Hole("Sleeve_Bore",0,0,inner/2,-0.1,length+0.2);
  Save(name,printable,0.72,0.72,0.72);
 }
 void SensorBracket() {
  if(Existing("Adjustable_ToF_Plate"))return;
  New("Adjustable_ToF_Plate");
  Box("Plate_54x30",-15,-27,15,27,0,2);
  Box("Optical_Window_10x10",-5,-5,5,5,-0.1,2.2,true);
  foreach(int s in new[]{-1,1})Box("Vertical_M3_Adjustment_"+s,-5,s*22-1.7,5,s*22+1.7,-0.1,2.2,true);
  Save("Adjustable_ToF_Plate",true,0.9,0.48,0.1);
 }
 void Coupon() {
  if(Existing("Shaft_and_Axle_Fit_Coupon"))return;
  New("Shaft_and_Axle_Fit_Coupon");Box("Coupon_120x25",-60,-12.5,60,12.5,0,4);
  double[] sizes={1.8,1.9,2.0,2.1,2.2,2.3,3.2,3.4,8.2,8.4,8.6};
  for(int i=0;i<sizes.Length;i++)Hole("Diameter_"+sizes[i].ToString().Replace('.','p'),-50+10*i,0,sizes[i]/2,-0.1,4.2);
  Box("Orientation_Notch",-60,-12.5,-56,-8.5,-0.1,4.2,true);
  Save("Shaft_and_Axle_Fit_Coupon",true,0.9,0.48,0.1);
 }
 void ReferenceBox(string name,double x,double y,double z,double r,double g,double b) {
  if(Existing(name))return;
  New(name);Box("REFERENCE_ENVELOPE_NOT_MANUFACTURING",-x/2,-y/2,x/2,y/2,0,z);Save(name,false,r,g,b);
 }
 void MotorReference() {
  if(Existing("REF_130_Motor_27p5x20x15_SHAFT2"))return;
  New("REF_130_Motor_27p5x20x15_SHAFT2");
  Box("Motor_Body_Envelope",-10,-7.5,10,7.5,0,27.5);
  Sketch();Circle(0,0,1);Finish("Reference_2mm_Shaft",27.5,8);
  Save("REF_130_Motor_27p5x20x15_SHAFT2",false,0.72,0.74,0.77);
 }
 void PrintedRearAxle() {
  if(Existing("Rear_Through_Axle_8mm_166L") && Existing("Rear_Axle_End_Cap"))return;
  New("Rear_Through_Axle_8mm_166L");Sketch();Circle(0,0,4);Finish("Axle_166mm",0,166);
  Box("Print_Bed_Flat_1mm",-5,-5,-3,5,-0.1,166.2,true);
  Save("Rear_Through_Axle_8mm_166L",true,0.95,0.55,0.12);
  New("Rear_Axle_End_Cap");Sketch();Circle(0,0,6);Finish("Retaining_Cap_12OD_8L",0,8);
  Hole("Blind_Axle_Socket_8p4",0,0,4.2,-0.1,5.6);
  Save("Rear_Axle_End_Cap",true,0.95,0.55,0.12);
 }
 void AxleReference() {
  if(Existing("REF_Rear_Axle_M3x30"))return;
  New("REF_Rear_Axle_M3x30");Sketch();Circle(0,0,1.5);Finish("Unthreaded_Envelope_M3x30",0,30);
  Sketch();Circle(0,0,2.75);Finish("Screw_Head_Envelope",30,2.4);
  Save("REF_Rear_Axle_M3x30",false,0.75,0.75,0.78);
 }
 IAssemblyDoc assy; IModelDoc2 assembly;
 void Component(string part,string label,double x,double y,double z,string rotation) {
  Say("Placing "+part);
  Component2 c=assy.AddComponent5(paths[part],0,"",false,"",0,0,0);
  if(c==null)throw new Exception("AddComponent failed "+part);
  double[] t={1,0,0,0,1,0,0,0,1,M(x),M(y),M(z),1,0,0,0};
  // SOLIDWORKS stores local basis vectors as rows.
  if(rotation=="AxleY") {t[0]=0;t[1]=0;t[2]=1;t[3]=1;t[4]=0;t[5]=0;t[6]=0;t[7]=1;t[8]=0;}
  if(rotation=="X-90") {t[4]=0;t[5]=-1;t[7]=1;t[8]=0;}
  if(rotation=="X90") {t[4]=0;t[5]=1;t[7]=-1;t[8]=0;}
  if(rotation=="X180") {t[4]=-1;t[8]=-1;}
  if(rotation=="Y90") {t[0]=0;t[2]=-1;t[6]=1;t[8]=0;}
  c.Transform2=(MathTransform)sw.IGetMathUtility().CreateTransform(t);
  c.Name2=label;
  assembly.ClearSelection2(true);
  c.Select4(false,null,false);assy.FixComponent();
 }
 void Assemble() {
  Say("Starting assembly creation");
  string at=sw.GetUserPreferenceStringValue(9);
  if(!File.Exists(at))at=@"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\MBD\assembly 0250mm and smaller.asmdot";
  Say("Assembly template "+at);
  assembly=(IModelDoc2)sw.NewDocument(at,0,0,0);assy=(IAssemblyDoc)assembly;
  Say("Created assembly document");
  if(assembly==null)throw new Exception("Assembly creation failed");
  assembly.SetUserPreferenceIntegerValue(263,5);
  Component("Chassis_FWD","PRINT_Chassis",0,0,0,"");
  Component("Flat_Webcam_Lid","PRINT_Removable_Flat_Lid",0,0,42,"X180");
  Component("Sloped_Webcam_Roof","PRINT_Roof_Pod",0,0,42,"");
  foreach(int side in new[]{-1,1}) {
   Component("Wheel_Arch_Trim","PRINT_Front_Arch_"+side,70,side>0?68:-65,13.5,"X90");
   Component("Wheel_Arch_Trim","PRINT_Rear_Arch_"+side,-95,side>0?68:-65,13.5,"X90");
   string rot=side>0?"X-90":"X90";
   Component("Front_Wheel_2mm_REFERENCE","PRINT_Front_Driven_Wheel_"+side,AxleX,side*67,AxleZ,rot);
   Component("Rear_Wheel_8p4mm_PrintedAxle","PRINT_Rear_Free_Wheel_"+side,-95,side*67,AxleZ,rot);
   Component("Rear_Axle_Spacer_1mm","PRINT_Rear_Spacer_"+side,-95,side*65,AxleZ,rot);
   Component("Rear_Axle_End_Cap","PRINT_Rear_Retainer_"+side,-95,side*78,AxleZ,rot);
   Component("REF_130_Motor_27p5x20x15_SHAFT2","REF_Front_Motor_"+side,AxleX,side*37.5,AxleZ,rot);
  }
  Component("Rear_Through_Axle_8mm_166L","PRINT_Continuous_Rear_Axle",-95,-83,AxleZ,"AxleY");
  Component("Adjustable_ToF_Plate","PRINT_Adjustable_ToF_Plate",105.4,0,21.5,"Y90");
  Component("REF_ToF_18x13x2","REF_ToF_PCB_TAPE_TO_PLATE",103.4,0,21.5,"Y90");
  Component("REF_Breadboard_170x55x10","REF_Breadboard",0,0,2.4,"");
  Component("REF_Nano_ENVELOPE_50x22x16","REF_Nano_USB_FACES_REAR",-65,0,12.4,"");
  Component("RESERVE_Battery_70x28x20","RESERVE_Battery_VERIFY_ACTUAL",-15,47,3,"");
  Component("RESERVE_Driver_45x28x15","RESERVE_Driver_VERIFY_ACTUAL",-15,-47,3,"");
  assembly.ClearSelection2(true);assembly.ForceRebuild3(false);assembly.ShowNamedView2("*Isometric",7);assembly.ViewZoomtofit2();
  int e=0,w=0;string output=Path.Combine(root,"WildlifeWatch_Rover_V3.SLDASM");
  if(!assembly.Extension.SaveAs(output,0,1,null,ref e,ref w)||e!=0)throw new Exception("Assembly save failed "+e);
  Say("Saved assembly: "+output);
 }
 public static string Run(string destination,bool resume) {
  BuildCar b=new BuildCar();b.root=destination;b.resume=resume;
  if(resume && File.Exists(Path.Combine(destination,"geometry_checks.csv"))) {
   string[] prior=File.ReadAllLines(Path.Combine(destination,"geometry_checks.csv"));
   for(int i=1;i<prior.Length;i++)if(prior[i].Length>0)b.report.Add(prior[i]);
  }
  Directory.CreateDirectory(Path.Combine(destination,"parts"));Directory.CreateDirectory(Path.Combine(destination,"stl_fit_check"));
  b.sw=(ISldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));
  b.sw.Visible=true;b.sw.UserControl=true;
  b.template=b.sw.GetUserPreferenceStringValue(8);
  if(!File.Exists(b.template))b.template=@"C:\ProgramData\SOLIDWORKS\SOLIDWORKS 2025\templates\MBD\part 0051mm to 0250mm.prtdot";
  int oldUnits=b.sw.GetUserPreferenceIntegerValue(211),oldQuality=b.sw.GetUserPreferenceIntegerValue(78);
  bool oldBinary=b.sw.GetUserPreferenceToggle(69),oldInfo=b.sw.GetUserPreferenceToggle(70),oldPreview=b.sw.GetUserPreferenceToggle(191);
  try {
   b.sw.SetUserPreferenceIntegerValue(211,0);b.sw.SetUserPreferenceIntegerValue(78,1);
   b.sw.SetUserPreferenceToggle(69,true);b.sw.SetUserPreferenceToggle(70,false);b.sw.SetUserPreferenceToggle(191,false);
   b.Chassis();b.Lid();b.RoofPod();b.ArchTrim();b.Wheel("Front_Wheel_2mm_REFERENCE",2.0);b.Wheel("Rear_Wheel_8p4mm_PrintedAxle",8.4);
   b.Ring("Rear_Axle_Spacer_1mm",12,8.6,1,true);b.PrintedRearAxle();
   b.SensorBracket();b.Coupon();b.MotorReference();
   b.ReferenceBox("REF_Breadboard_170x55x10",170,55,10,0.9,0.9,0.85);
   b.ReferenceBox("REF_Nano_ENVELOPE_50x22x16",50,22,16,0.1,0.5,0.35);
   b.ReferenceBox("REF_ToF_18x13x2",18,13,2,0.5,0.1,0.15);
   b.ReferenceBox("RESERVE_Battery_70x28x20",70,28,20,0.3,0.25,0.4);
   b.ReferenceBox("RESERVE_Driver_45x28x15",45,28,15,0.5,0.2,0.15);
   b.Assemble();
  } finally {
   b.sw.SetUserPreferenceIntegerValue(211,oldUnits);b.sw.SetUserPreferenceIntegerValue(78,oldQuality);
   b.sw.SetUserPreferenceToggle(69,oldBinary);b.sw.SetUserPreferenceToggle(70,oldInfo);b.sw.SetUserPreferenceToggle(191,oldPreview);
   File.WriteAllLines(Path.Combine(destination,"geometry_checks.csv"),new[]{"part,type,x_mm,y_mm,z_mm,volume_mm3,solid_bodies,body_check_code"});
   File.AppendAllLines(Path.Combine(destination,"geometry_checks.csv"),b.report);
  }
  return "Completed reference CAD layout; physical fit and drivetrain remain unverified.";
 }
}
