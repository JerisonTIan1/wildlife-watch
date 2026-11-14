using System;
using System.IO;
using System.Collections.Generic;
using System.Globalization;
using SolidWorks.Interop.sldworks;
public static class FinishParts {
 public static void Run(string root) {
  ISldWorks sw=(ISldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));
  sw.Visible=true;sw.UserControl=true;int e=0,w=0;
  string roof=Path.Combine(root,"parts","Sloped_Webcam_Roof_V3.SLDPRT");
  IModelDoc2 m=sw.OpenDoc6(roof,1,1,"",ref e,ref w);
  if(m==null)throw new Exception("Cannot open roof: "+e);
  sw.ActivateDoc3(m.GetTitle(),false,0,ref e);
  Feature f=(Feature)((IPartDoc)m).FeatureByName("Sloped_45deg_Roof_Flat_Webcam_Top");
  IExtrudeFeatureData2 d=(IExtrudeFeatureData2)f.GetDefinition();
  if(d.GetDraftOutward(true)) {
   if(!d.AccessSelections(m,null))throw new Exception("Roof selection access failed");
   d.SetDraftOutward(true,false);
   if(!f.ModifyDefinition(d,m,null))throw new Exception("Roof taper modification failed");
  }
  m.ForceRebuild3(false);m.Save3(1,ref e,ref w);
  if(e!=0)throw new Exception("Roof save error: "+e);
  int units=sw.GetUserPreferenceIntegerValue(211),quality=sw.GetUserPreferenceIntegerValue(78);
  bool bin=sw.GetUserPreferenceToggle(69),info=sw.GetUserPreferenceToggle(70),preview=sw.GetUserPreferenceToggle(191);
  try {
   sw.SetUserPreferenceIntegerValue(211,0);sw.SetUserPreferenceIntegerValue(78,1);
   sw.SetUserPreferenceToggle(69,true);sw.SetUserPreferenceToggle(70,false);sw.SetUserPreferenceToggle(191,false);
   if(!m.Extension.SaveAs(Path.Combine(root,"stl_fit_check","Sloped_Webcam_Roof.STL"),0,1,null,ref e,ref w)||e!=0)throw new Exception("Roof STL save failed");
  } finally {
   sw.SetUserPreferenceIntegerValue(211,units);sw.SetUserPreferenceIntegerValue(78,quality);
   sw.SetUserPreferenceToggle(69,bin);sw.SetUserPreferenceToggle(70,info);sw.SetUserPreferenceToggle(191,preview);
  }
  var rows=new List<string>();rows.Add("part,type,x_mm,y_mm,z_mm,volume_mm3,solid_bodies,body_check_code");
  foreach(string path in Directory.GetFiles(Path.Combine(root,"parts"),"*.SLDPRT")) {
   if(Path.GetFileName(path).StartsWith("~$"))continue;
   m=sw.OpenDoc6(path,1,1,"",ref e,ref w);if(m==null)throw new Exception("Cannot reopen "+path+" "+e);
   object[] bodies=(object[])((IPartDoc)m).GetBodies2(0,false);
   if(bodies==null || bodies.Length!=1 || ((IBody2)bodies[0]).Check2()!=0)throw new Exception("Invalid solid: "+path);
   IBody2 b=(IBody2)bodies[0];double[] lo=new double[3],hi=new double[3];
   for(int axis=0;axis<3;axis++)foreach(int sign in new[]{-1,1}) {
    double x,y,z;double[] dir={0,0,0};dir[axis]=sign;
    if(!b.GetExtremePoint(dir[0],dir[1],dir[2],out x,out y,out z))throw new Exception("Bounds failed");
    double value=new double[]{x,y,z}[axis]*1000;if(sign<0)lo[axis]=value;else hi[axis]=value;
   }
   double[] mass=(double[])b.GetMassProperties(1);
   string name=Path.GetFileNameWithoutExtension(path).Replace("_V3","");
   string type=name.StartsWith("REF_")||name.StartsWith("RESERVE_")?"REFERENCE":"PRINT";
   rows.Add(String.Format(CultureInfo.InvariantCulture,"{0},{1},{2:F3},{3:F3},{4:F3},{5:F3},1,0",name,type,hi[0]-lo[0],hi[1]-lo[1],hi[2]-lo[2],mass[3]*1e9));
  }
  File.WriteAllLines(Path.Combine(root,"geometry_checks.csv"),rows);
  Console.WriteLine("Inward roof taper saved; native solids validated: "+(rows.Count-1));
 }
}
