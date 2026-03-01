import streamlit as st
import google.generativeai as genai
import chromadb
from pypdf import PdfReader
import os
import glob

# Configurar la IA
# BORRÁ LA LÍNEA VIEJA Y PONÉ ESTA:
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
modelo = genai.GenerativeModel('gemini-2.5-flash')

# Iniciar la Base de Datos
cliente_chroma = chromadb.PersistentClient(path="./base_manuales")
coleccion = cliente_chroma.get_or_create_collection(name="control_calidad")

st.title("Chat del Laboratorio - Molinos Agro")

# Panel lateral
with st.sidebar:
    st.header("Base de Conocimiento")
    
    # OPCIÓN 1: Subir archivos manualmente
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
                    
                    # Usamos UPSERT para que si lo subís de nuevo, lo actualice en vez de duplicarlo o dar error
                    coleccion.upsert(documents=pedazos, ids=ids, metadatas=metadatos)
            st.success("¡Archivos procesados correctamente!")
        else:
            st.warning("Primero seleccioná un archivo.")

    st.divider()

    # OPCIÓN 2: Sincronizar desde una carpeta local
    st.subheader("Opción 2: Leer desde Carpeta")
    # Por defecto busca en una carpeta llamada "manuales" al lado de app.py
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

# Historial del Chat
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
        
        prompt = f"""Sos un analista experto del laboratorio de control de calidad. 
        Respondé la siguiente consulta de forma técnica, directa y basándote ÚNICAMENTE en este texto de los procedimientos.
        Si la información no está en el texto proporcionado, respondé exactamente: "Esa información no figura en los manuales cargados."
        
        TEXTO DE LOS MANUALES:
        {contexto}
        
        CONSULTA: {pregunta}"""
        
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
