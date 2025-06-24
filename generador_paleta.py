import bpy
import numpy as np
from sklearn.cluster import KMeans
from PIL import Image # Para cargar la imagen, PIL es más robusto

# --- INFORMACIÓN DEL ADD-ON (PARA INSTALARLO DESPUÉS) ---
bl_info = {
    "name": "Generador de Paleta por Imagen",
    "author": "Tu Nombre (opcional)",
    "version": (1, 1), # Incrementada la versión por los cambios
    "blender": (4, 0, 0),
    "location": "3D View > Sidebar > Paleta",
    "description": "Extrae colores dominantes únicos de una imagen y crea materiales y objetos de referencia.",
    "warning": "",
    "doc_url": "",
    "category": "Material",
}

# --- CONFIGURACIÓN (PUEDES CAMBIAR ESTOS VALORES) ---
NUM_COLORES_PALETA = 8
CREAR_OBJETOS_DE_REFERENCIA = True
REESCALAR_IMAGEN_PROCESAMIENTO = 0.3
PREFIJO_NOMBRE_DEFAULT = "Paleta_"

# NUEVA CONFIGURACIÓN: Tolerancia para la detección de colores similares
# Cuanto menor el valor, más estrictos serán los colores "únicos".
# Un valor de 0.05 significa que si la diferencia RGB es muy pequeña, se considera el mismo color.
TOLERANCIA_COLOR_UNICOS = 0.05 

# --- FUNCIONES PRINCIPALES ---
def extraer_paleta_de_imagen(imagen_path, num_colores=NUM_COLORES_PALETA, 
                             reescalar_factor=REESCALAR_IMAGEN_PROCESAMIENTO,
                             tolerancia_unicos=TOLERANCIA_COLOR_UNICOS): # Nuevo parámetro
    try:
        img = Image.open(imagen_path)
        img = img.convert('RGB')

        if reescalar_factor > 0 and reescalar_factor < 1:
            ancho_original, alto_original = img.size
            nuevo_ancho = int(ancho_original * reescalar_factor)
            nuevo_alto = int(alto_original * reescalar_factor)
            img_redimensionada = img.resize((nuevo_ancho, nuevo_alto), Image.LANCZOS)
            data = np.array(img_redimensionada)
        else:
            data = np.array(img)

        pixels = data.reshape(-1, 3)

        kmeans = KMeans(n_clusters=num_colores, random_state=0, n_init=10)
        kmeans.fit(pixels)

        colores_rgb_normalizados = kmeans.cluster_centers_ / 255.0

        # --- NUEVA LÓGICA PARA FILTRAR COLORES MUY SIMILARES ---
        colores_finales_unicos = []
        for new_color in colores_rgb_normalizados:
            is_unique = True
            for existing_color in colores_finales_unicos:
                # Calcular la distancia euclidiana entre los colores
                distance = np.linalg.norm(new_color - existing_color)
                if distance < tolerancia_unicos:
                    is_unique = False
                    break # No es único, salimos del bucle interno
            if is_unique:
                colores_finales_unicos.append(new_color)
        # --- FIN DE LA NUEVA LÓGICA ---

        return colores_finales_unicos # Devolvemos los colores filtrados

    except FileNotFoundError:
        print(f"Error: La imagen no se encontró en la ruta: {imagen_path}")
        return None
    except Exception as e:
        print(f"Error al procesar la imagen: {e}")
        return None

def crear_material_desde_color(nombre_material, rgb_color):
    mat = bpy.data.materials.new(name=nombre_material)
    mat.use_nodes = False
    mat.diffuse_color = (rgb_color[0], rgb_color[1], rgb_color[2], 1.0)
    return mat

def crear_esferas_de_paleta(colores, prefijo_nombre=PREFIJO_NOMBRE_DEFAULT):
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5)
    base_esfera = bpy.context.active_object
    base_esfera.name = f"{prefijo_nombre}00"

    for i, color_rgb in enumerate(colores):
        if i == 0:
            obj = base_esfera
        else:
            bpy.ops.object.duplicate()
            obj = bpy.context.active_object
            obj.location.x = i * 1.5
            obj.name = f"{prefijo_nombre}{i:02d}"

        mat_name = f"{prefijo_nombre}{i:02d}"
        material = crear_material_desde_color(mat_name, color_rgb)

        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)

def limpiar_materiales_paleta(context):
    current_prefix = context.scene.image_generar_paleta_settings.prefijo_nombre

    materials_to_remove = [
        mat for mat in bpy.data.materials
        if mat.name.startswith(PREFIJO_NOMBRE_DEFAULT) or
           mat.name.startswith(current_prefix)
    ]
    for mat in materials_to_remove:
        if not mat.users:
            bpy.data.materials.remove(mat)

    objects_to_remove = [
        obj for obj in bpy.data.objects
        if obj.name.startswith(PREFIJO_NOMBRE_DEFAULT) or
           obj.name.startswith(current_prefix) or
           "Color_Referencia_" in obj.name
    ]
    for obj in objects_to_remove:
        bpy.data.objects.remove(obj, do_unlink=True)


# --- CLASE OPERADOR DE BLENDER (EL BOTÓN QUE APARECE EN LA INTERFAZ) ---
class IMAGEN_OT_GenerarPaleta(bpy.types.Operator):
    bl_idname = "image.generar_paleta"
    bl_label = "Generar Paleta de Imagen"
    bl_description = "Extrae colores dominantes únicos de una imagen y crea materiales y/o esferas de referencia."
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(
        name="Ruta de Imagen",
        subtype='FILE_PATH',
        description="Selecciona la imagen de referencia para extraer la paleta de colores."
    )

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "Por favor, selecciona una imagen primero.")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Procesando imagen: {self.filepath}")

        settings = context.scene.image_generar_paleta_settings
        num_colores = settings.num_colores_paleta
        crear_objetos = settings.crear_objetos_referencia
        reescalar_factor = settings.reescalar_imagen_procesamiento
        prefijo_nombre = settings.prefijo_nombre
        tolerancia_colores = settings.tolerancia_color_unicos # Obtener la nueva configuración

        limpiar_materiales_paleta(context)

        # Pasar la nueva tolerancia a la función de extracción
        colores_extraidos = extraer_paleta_de_imagen(
            self.filepath,
            num_colores=num_colores,
            reescalar_factor=reescalar_factor,
            tolerancia_unicos=tolerancia_colores # Pasar la tolerancia
        )

        if colores_extraidos is None or len(colores_extraidos) == 0:
            self.report({'ERROR'}, "No se pudieron extraer colores de la imagen. Verifica la ruta o el archivo.")
            return {'CANCELLED'}

        if crear_objetos:
            crear_esferas_de_paleta(colores_extraidos, prefijo_nombre=prefijo_nombre)
            self.report({'INFO'}, f"Paleta de {len(colores_extraidos)} colores únicos generada y aplicada a esferas.")
        else:
            for i, color_rgb in enumerate(colores_extraidos):
                mat_name = f"{prefijo_nombre}{i:02d}"
                crear_material_desde_color(mat_name, color_rgb)
            self.report({'INFO'}, f"Paleta de {len(colores_extraidos)} colores únicos generada (solo materiales).")

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


# --- CLASE PARA ALMACENAR CONFIGURACIONES DE USUARIO ---
class GenerarPaletaSettings(bpy.types.PropertyGroup):
    num_colores_paleta: bpy.props.IntProperty(
        name="Número de Colores",
        description="Cantidad de colores dominantes a extraer.",
        default=NUM_COLORES_PALETA,
        min=2,
        max=64
    )
    crear_objetos_referencia: bpy.props.BoolProperty(
        name="Crear Esferas de Referencia",
        description="Si está marcado, se crearán esferas con cada color de la paleta.",
        default=CREAR_OBJETOS_DE_REFERENCIA
    )
    reescalar_imagen_procesamiento: bpy.props.FloatProperty(
        name="Escala de Procesamiento",
        description="Factor de reescalado de la imagen para el procesamiento (0.1 = 10%). Reduce el tiempo para imágenes grandes.",
        default=REESCALAR_IMAGEN_PROCESAMIENTO,
        min=0.01,
        max=1.0
    )
    prefijo_nombre: bpy.props.StringProperty(
        name="Prefijo Nombres",
        description="Prefijo para los nombres de las esferas y materiales (ej. 'MiProyecto_').",
        default=PREFIJO_NOMBRE_DEFAULT,
    )
    # NUEVA PROPIEDAD: Tolerancia para colores únicos
    tolerancia_color_unicos: bpy.props.FloatProperty(
        name="Tolerancia Unicidad Color",
        description="Valor de tolerancia para considerar dos colores como 'iguales'. Menor valor = más estrictos (0.0 a 1.0).",
        default=TOLERANCIA_COLOR_UNICOS,
        min=0.0,
        max=0.1, # <--- Esta es la línea que vamos a cambiar
        precision=3 # Mostrar 3 decimales
    )

# --- PANEL DE LA INTERFAZ DE USUARIO (PESTAÑA PERSONALIZADA) ---
class VIEW3D_PT_PaletaInteligente(bpy.types.Panel):
    bl_label = "Paleta Inteligente"
    bl_idname = "VIEW3D_PT_paleta_inteligente"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Paleta"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Generador de Colores", icon='COLOR')
        
        row = box.row(align=True)
        row.prop(context.scene.image_generar_paleta_settings, "num_colores_paleta", text="Nº Colores")
        row.prop(context.scene.image_generar_paleta_settings, "reescalar_imagen_procesamiento", text="Escala Proceso")
        
        row = box.row(align=True)
        row.prop(context.scene.image_generar_paleta_settings, "crear_objetos_referencia", text="Crear Esferas Ref.")
        
        box.prop(context.scene.image_generar_paleta_settings, "prefijo_nombre") 
        box.prop(context.scene.image_generar_paleta_settings, "tolerancia_color_unicos") # Añadido al panel
        
        box.operator(IMAGEN_OT_GenerarPaleta.bl_idname, text="Generar Paleta desde Imagen", icon='IMAGE_DATA')


# --- REGISTRO Y DESREGISTRO DEL ADD-ON ---
def register():
    bpy.utils.register_class(GenerarPaletaSettings)
    bpy.types.Scene.image_generar_paleta_settings = bpy.props.PointerProperty(type=GenerarPaletaSettings)
    
    bpy.utils.register_class(IMAGEN_OT_GenerarPaleta)
    
    bpy.utils.register_class(VIEW3D_PT_PaletaInteligente)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_PaletaInteligente)
    
    bpy.utils.unregister_class(IMAGEN_OT_GenerarPaleta)
    
    del bpy.types.Scene.image_generar_paleta_settings
    bpy.utils.unregister_class(GenerarPaletaSettings)


# --- PUNTO DE ENTRADA PARA EJECUTAR EN EL EDITOR DE TEXTO ---
if __name__ == "__main__":
    try:
        unregister()
    except Exception:
        pass
    
    register()

    print("Script 'Generar Paleta de Colores' cargado. Ve a la barra lateral (N-panel) en la vista 3D, en la pestaña 'Paleta'.")