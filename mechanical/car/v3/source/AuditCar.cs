using System;
using System.IO;
using System.Collections.Generic;
using SolidWorks.Interop.sldworks;
public static class AuditCar {
 public static void Run(string root) {
  ISldWorks sw=(ISldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));
  int e=0,w=0;
  IModelDoc2 m=sw.OpenDoc6(Path.Combine(root,"WildlifeWatch_Rover_V3.SLDASM"),2,1,"",ref e,ref w);
  if(m==null)throw new Exception("Open failed "+e);
  sw.ActivateDoc3(m.GetTitle(),false,0,ref e);
  IAssemblyDoc a=(IAssemblyDoc)m;
  var rows=new List<string>();rows.Add("component,origin_x_mm,origin_y_mm,origin_z_mm");
  foreach(IComponent2 c in (object[])a.GetComponents(false)) {
   double[] t=(double[])c.Transform2.ArrayData;
   rows.Add(c.Name2+","+(1000*t[9])+","+(1000*t[10])+","+(1000*t[11]));
  }
  File.WriteAllLines(Path.Combine(root,"assembly_positions.csv"),rows);
  // Exact directional extrema of every solid, transformed into assembly coordinates.
  double[] lo={double.PositiveInfinity,double.PositiveInfinity,double.PositiveInfinity};
  double[] hi={double.NegativeInfinity,double.NegativeInfinity,double.NegativeInfinity};
  foreach(IComponent2 c in (object[])a.GetComponents(false)) {
   double[] t=(double[])c.Transform2.ArrayData;IPartDoc part=(IPartDoc)c.GetModelDoc2();
   foreach(IBody2 b in (object[])part.GetBodies2(0,false))foreach(int axis in new[]{0,1,2})foreach(int sign in new[]{-1,1}) {
    double x=0,y=0,z=0;
    if(!b.GetExtremePoint(sign*t[axis],sign*t[3+axis],sign*t[6+axis],out x,out y,out z))throw new Exception("Extreme point failed");
    double value=(x*t[axis]+y*t[3+axis]+z*t[6+axis]+t[9+axis])*1000;
    lo[axis]=Math.Min(lo[axis],value);hi[axis]=Math.Max(hi[axis],value);
   }
  }
  var dims=new List<string>();dims.Add("axis,min_mm,max_mm,size_mm");
  for(int i=0;i<3;i++)dims.Add("XYZ"[i]+","+lo[i]+","+hi[i]+","+(hi[i]-lo[i]));
  File.WriteAllLines(Path.Combine(root,"overall_dimensions.csv"),dims);
  Console.WriteLine("Overall mm: "+(hi[0]-lo[0])+" x "+(hi[1]-lo[1])+" x "+(hi[2]-lo[2]));
  IInterferenceDetectionMgr mgr=a.InterferenceDetectionManager;
  mgr.TreatCoincidenceAsInterference=false;mgr.IgnoreHiddenBodies=false;
  mgr.IncludeMultibodyPartInterferences=true;mgr.UseTransform=false;
  object[] results=mgr.GetInterferences() as object[];
  rows.Clear();rows.Add("volume_mm3,components");
  if(results!=null)foreach(IInterference hit in results) {
   var names=new List<string>();foreach(IComponent2 c in (object[])hit.Components)names.Add(c.Name2);
   rows.Add((hit.Volume*1e9).ToString("G12")+","+String.Join(" | ",names));
  }
  File.WriteAllLines(Path.Combine(root,"interferences.csv"),rows);
  Console.WriteLine("Interferences: "+(results==null?0:results.Length));foreach(string s in rows)Console.WriteLine(s);
  // Positive control: briefly move the battery reserve into the floor, restore immediately.
  foreach(IComponent2 c in (object[])a.GetComponents(false))if(c.GetPathName().EndsWith("RESERVE_Battery_70x28x20_V3.SLDPRT")) {
   MathTransform original=c.Transform2;
   try {
    double[] t=(double[])original.ArrayData;t[11]=-0.005;
    c.Transform2=(MathTransform)sw.IGetMathUtility().CreateTransform(t);m.ForceRebuild3(false);
    int hits=mgr.GetInterferenceCount();Console.WriteLine("Positive-control collision count: "+hits);
    if(hits<1)throw new Exception("Interference detection failed its positive control");
   } finally {c.Transform2=original;m.ForceRebuild3(false);m.ClearSelection2(true);}
   break;
  }
  int restored=mgr.GetInterferenceCount();Console.WriteLine("Restored interference count: "+restored);
  if(restored!=0)throw new Exception("Unresolved model interference");
  m.Save3(1,ref e,ref w);
 }
}
