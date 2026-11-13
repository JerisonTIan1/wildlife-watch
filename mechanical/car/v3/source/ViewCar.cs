using System;
using System.IO;
using SolidWorks.Interop.sldworks;
public static class ViewCar {
 public static void Run(string root,bool open) {
  ISldWorks sw=(ISldWorks)Activator.CreateInstance(Type.GetTypeFromProgID("SldWorks.Application"));int e=0,w=0;
  IModelDoc2 m=sw.OpenDoc6(Path.Combine(root,"WildlifeWatch_Rover_V3.SLDASM"),2,1,"",ref e,ref w);
  sw.ActivateDoc3(m.GetTitle(),false,0,ref e);
  m.SetUserPreferenceIntegerValue(263,5);
  for(int i=0;i<m.GetLightSourceCount();i++) {
   double[] light=(double[])m.get_LightSourcePropertyValues(i);
   Console.WriteLine("Light "+i+" "+m.GetLightSourceName(i)+": "+String.Join(" ",light));
   if(i==0){light[15]=0.8;light[17]=0;m.set_LightSourcePropertyValues(i,light);}
  }
  var savedParts=new System.Collections.Generic.HashSet<string>();
  foreach(IComponent2 c in (object[])((IAssemblyDoc)m).GetComponents(false)) {
   string path=c.GetPathName();
   if(path.EndsWith("Flat_Webcam_Lid_V3.SLDPRT") || path.EndsWith("Sloped_Webcam_Roof_V3.SLDPRT"))c.Visible=open?0:1;
   if(path.EndsWith("Adjustable_ToF_Plate_V3.SLDPRT") || path.EndsWith("REF_ToF_18x13x2_V3.SLDPRT")) {
    double[] ct=(double[])c.Transform2.ArrayData;ct[11]=0.0215;
    c.Transform2=(MathTransform)sw.IGetMathUtility().CreateTransform(ct);
   }
   if(savedParts.Add(path)) {
    IModelDoc2 part=(IModelDoc2)c.GetModelDoc2();part.SetUserPreferenceIntegerValue(263,5);double[] mat=(double[])part.MaterialPropertyValues;
    mat[3]=0.9;
    if(path.EndsWith("Chassis_FWD_V3.SLDPRT")){mat[0]=0.22;mat[1]=0.56;mat[2]=0.68;}
    part.MaterialPropertyValues=mat;part.Save3(1,ref e,ref w);
   }
  }
  double s=Math.Sqrt(0.5),u=1/Math.Sqrt(6.0),v=1/Math.Sqrt(3.0);
  double[] t={s,-u,v,s,u,-v,0,2*u,v,0,0,0,1,0,0,0};
  IModelView view=(IModelView)m.ActiveView;
  view.Orientation3=(MathTransform)sw.IGetMathUtility().CreateTransform(t);
  m.ClearSelection2(true);m.ViewDisplayShaded();m.ViewZoomtofit2();m.GraphicsRedraw2();
  string tag=open?"interior":"exterior";
  bool saved=m.SaveBMP(Path.Combine(root,tag+".bmp"),1600,1000);
  Console.WriteLine("Preview "+tag+" saved="+saved);
  if(open) {
   var visibility=new System.Collections.Generic.Dictionary<IComponent2,int>();
   try {
    foreach(IComponent2 c in (object[])((IAssemblyDoc)m).GetComponents(false)) {
     visibility[c]=c.Visible;c.Visible=Path.GetFileName(c.GetPathName()).StartsWith("Rear_")?1:0;
    }
    m.ClearSelection2(true);m.ViewZoomtofit2();m.GraphicsRedraw2();
    Console.WriteLine("Rear axle detail="+m.SaveBMP(Path.Combine(root,"rear_axle_detail.bmp"),1600,800));
   } finally {
    foreach(var entry in visibility)entry.Key.Visible=entry.Value;
    m.ViewZoomtofit2();m.GraphicsRedraw2();
   }
  }
  m.Save3(1,ref e,ref w);Console.WriteLine("Assembly saved, errors="+e);
 }
}
