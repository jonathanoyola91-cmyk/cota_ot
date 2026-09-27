from django.db import migrations, models
import django.db.models.deletion

def crear_tipos(apps, schema_editor):
    Tipo = apps.get_model('taller','TipoPiezaMetrologia')
    Plantilla = apps.get_model('taller','PlantillaEje')
    nombres={'EJE':'Eje','HOUSING':'Housing','SLEEVE':'Sleeve / camisa','CAMARA':'Cámara','BOMBA':'Bomba','OTRO':'Otra pieza'}
    creados={}
    for k,n in nombres.items():
        obj,_=Tipo.objects.get_or_create(nombre=n)
        creados[k]=obj
    for p in Plantilla.objects.all():
        p.tipo_pieza_ref=creados.get(p.tipo_pieza,creados['OTRO'])
        p.save(update_fields=['tipo_pieza_ref'])

class Migration(migrations.Migration):
    dependencies=[('taller','0013_plantillas_genericas_metrologia')]
    operations=[
        migrations.CreateModel(name='TipoPiezaMetrologia',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('nombre',models.CharField(max_length=100,unique=True)),('activo',models.BooleanField(default=True)),('orden',models.PositiveIntegerField(default=0))],options={'ordering':['orden','nombre']}),
        migrations.AddField(model_name='plantillaeje',name='tipo_pieza_ref',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name='plantillas',to='taller.tipopiezametrologia')),
        migrations.AddField(model_name='puntomedicioneje',name='minimo_reutilizable',field=models.DecimalField(blank=True,decimal_places=4,help_text='Límite mínimo para reutilización en reparaciones',max_digits=12,null=True)),
        migrations.AddField(model_name='puntomedicioneje',name='permite_mecanizado',field=models.BooleanField(default=True,help_text='Permite recuperar este punto mediante mecanizado autorizado')),
        migrations.AddField(model_name='inspeccioneje',name='tipo_trabajo',field=models.CharField(choices=[('REPARACION','Reparación'),('FABRICACION','Fabricación')],default='REPARACION',max_length=20)),
        migrations.RunPython(crear_tipos,migrations.RunPython.noop),
    ]
