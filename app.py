import streamlit as st
import google.generativeai as genai
import chromadb
from pypdf import PdfReader
import os
import glob

# 1. Configuración de página (DEBE IR PRIMERO)
st.set_page_config(page_title="Lab Molinos Agro", page_icon="🌾", layout="wide")

# 2. Inyección de CSS (Estética Molinos Agro)
estilo_molinos = """
<style>
    /* Fondo principal blanco/gris muy claro */
    .stApp {
        background-color: #F8F9FA;
    }
    /* Título principal Azul */
    h1 {
        color: #004B87 !important; /* Azul corporativo */
        font-family: 'Helvetica Neue', sans-serif;
        font-weight: 700;
    }
    /* Panel lateral Verde */
    [data-testid="stSidebar"] {
        background-color: #005C3A; /* Verde corporativo */
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    /* Botones Azules */
    div.stButton > button:first-child {
        background-color: #004B87 !important; /* Azul corporativo */
        color: white !important;
        font-weight: bold;
        border: none;
        border-radius: 8px;
        transition: all 0.3s;
    }
    div.stButton > button:first-child:hover {
        background-color: #00335c !important; /* Azul más oscuro al pasar el mouse */
        transform: scale(1.02);
    }
    /* Cajas de chat Blancas con detalle Verde */
    [data-testid="stChatMessage"] {
        background-color: white;
        border-radius: 10px;
        padding: 10px;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.05);
        border-left: 5px solid #005C3A;
        margin-bottom: 10px;
    }
    
    /* --- NUEVOS CAMBIOS: ICONOS Y RECUADRO --- */
    
    /* Borde del recuadro de texto a Verde y eliminar el rojo/rosa por defecto */
    [data-testid="stChatInput"] {
        border-color: #005C3A !important;
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: #005C3A !important;
        box-shadow: 0 0 0 2px #005C3A !important;
        outline: none !important;
    }
    [data-testid="stChatInput"] textarea:focus {
        box-shadow: none !important;
        outline: none !important;
    }
    
    /* Color del Icono del Usuario (Azul) */
    [data-testid="stChatMessageAvatarUser"] {
        background-color: #004B87 !important;
    }
    /* Color del Icono del Asistente (Verde) */
    [data-testid="stChatMessageAvatarAssistant"] {
        background-color: #005C3A !important;
    }
</style>
"""
st.markdown(estilo_molinos, unsafe_allow_html=True)

# Configurar la IA
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
modelo = genai.GenerativeModel('gemini-2.5-flash')

# Iniciar la Base de Datos
cliente_chroma = chromadb.PersistentClient(path="./base_manuales")
coleccion = cliente_chroma.get_or_create_collection(name="control_calidad")

st.title("Asistente de Laboratorio")

# Panel lateral
with st.sidebar:
    # Espacio para el logo (si subís 'logo.png' a GitHub, se muestra acá)
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.header("MOLINOS AGRO")
        
    st.divider()
    st.subheader("Opción 1: Subir manual")
    archivos = st.file_uploader("Subir manuales (PDF)", type=["pdf"], accept_multiple_files=True)
    if st.button("Procesar Archivos Sueltos"):
        if archivos:
            with st.spinner('Guardando textos y fuentes...'):
                for archivo in archivos:
                    lector = PdfReader(archivo)
                    texto_completo = ""
                    for pagina in lector.pages:
                        texto_completo += pagina.extract_text() + "\n"
                    
                    pedazos = []
                    for i in range(0, len(texto_completo), 800):
                        pedazos.append(texto_completo[i:i+1000])
                        
                    ids = [f"{archivo.name}_{i}" for i in range(len(pedazos))]
                    metadatos = [{"fuente": archivo.name} for _ in range(len(pedazos))]
                    
                    coleccion.upsert(documents=pedazos, ids=ids, metadatas=metadatos)
            st.success("¡Archivos procesados correctamente!")
        else:
            st.warning("Primero seleccioná un archivo.")

    st.divider()

    st.subheader("Opción 2: Leer desde Carpeta")
    ruta_carpeta = st.text_input("Ruta de la carpeta:", value="./manuales") 
    
    if st.button("Sincronizar Carpeta"):
        if os.path.exists(ruta_carpeta):
            archivos_pdf = glob.glob(os.path.join(ruta_carpeta, "*.pdf"))
            if archivos_pdf:
                with st.spinner(f'Procesando {len(archivos_pdf)} archivos...'):
                    for ruta_archivo in archivos_pdf:
                        nombre_archivo = os.path.basename(ruta_archivo)
                        lector = PdfReader(ruta_archivo)
                        texto_completo = ""
                        for pagina in lector.pages:
                            if pagina.extract_text():
                                texto_completo += pagina.extract_text() + "\n"
                        
                        if texto_completo.strip():
                            pedazos = []
                            for i in range(0, len(texto_completo), 800):
                                pedazos.append(texto_completo[i:i+1000])
                                
                            ids = [f"{nombre_archivo}_{i}" for i in range(len(pedazos))]
                            metadatos = [{"fuente": nombre_archivo} for _ in range(len(pedazos))]
                            
                            coleccion.upsert(documents=pedazos, ids=ids, metadatas=metadatos)
                st.success(f"¡{len(archivos_pdf)} manuales sincronizados!")
            else:
                st.warning("No se encontraron PDFs en esa carpeta.")
        else:
            st.error("La carpeta no existe. Creala o revisá la ruta.")

# Historial del Chat en pantalla
if "mensajes" not in st.session_state:
    st.session_state.mensajes = []

for mensaje in st.session_state.mensajes:
    with st.chat_message(mensaje["rol"]):
        st.markdown(mensaje["contenido"])

# Caja de preguntas
if pregunta := st.chat_input("Escribí tu consulta sobre los procedimientos..."):
    with st.chat_message("user"):
        st.markdown(pregunta)
    st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
    
    # Buscar en ChromaDB
    resultados = coleccion.query(query_texts=[pregunta], n_results=5)
    
    if resultados['documents'] and resultados['documents'][0]:
        contexto = "\n".join(resultados['documents'][0])
        
        fuentes_usadas = list(set([meta.get('fuente', 'Manual desconocido') for meta in resultados['metadatas'][0] if meta is not None]))
        texto_fuentes = ", ".join(fuentes_usadas)
        
        # Armar el historial reciente
        historial_texto = ""
        if len(st.session_state.mensajes) > 1:
            historial_texto = "\nHISTORIAL DE LA CONVERSACIÓN:\n"
            for msg in st.session_state.mensajes[-5:-1]:
                rol = "Usuario" if msg["rol"] == "user" else "Asistente"
                historial_texto += f"{rol}: {msg['contenido']}\n"
        
        prompt = f"""Sos un analista experto del laboratorio de control de calidad. 
        Respondé la siguiente consulta de forma técnica, directa y basándote ÚNICAMENTE en este texto de los procedimientos.
        Si la información no está en el texto proporcionado, respondé exactamente: "Esa información no figura en los manuales cargados."
        
        TEXTO DE LOS MANUALES:
        {contexto}
        {historial_texto}
        
        CONSULTA ACTUAL: {pregunta}"""
        
        try:
            respuesta = modelo.generate_content(prompt).text
            respuesta += f"\n\n*(Fuentes consultadas: {texto_fuentes})*"
        except Exception as e:
            respuesta = f"Error devuelto por Google: {e}"
            
    else:
        respuesta = "No hay información en la base de datos para responder esto."
        
    with st.chat_message("assistant"):
        st.markdown(respuesta)
    st.session_state.mensajes.append({"rol": "assistant", "contenido": respuesta})
