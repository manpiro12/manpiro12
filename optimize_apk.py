#!/usr/bin/env python3
"""
APK Optimizer - Convierte archivos .dex de DEFLATED a STORED
para mejorar compatibilidad en dispositivos de gama baja como Infinix Smart 8.

El problema: Los archivos .dex comprimidos (DEFLATED) causan crashes en dispositivos
con poca memoria. La solución: Almacenarlos sin compresión (STORED).
"""

import os
import sys
import shutil
import zipfile
import subprocess
import tempfile
import argparse
from pathlib import Path


def download_apk(repo: str, output_dir: str = ".") -> str:
    """
    Descarga el APK más reciente desde los releases de GitHub.
    
    Args:
        repo: Repositorio en formato "owner/repo"
        output_dir: Directorio donde guardar el APK
        
    Returns:
        Ruta al archivo APK descargado
    """
    import requests
    
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    print(f"📥 Descargando release info desde: {url}")
    
    response = requests.get(url)
    response.raise_for_status()
    
    assets = response.json().get('assets', [])
    apk_assets = [a for a in assets if a['name'].endswith('.apk')]
    
    if not apk_assets:
        raise Exception("❌ No se encontró ningún APK en el release más reciente.")
    
    apk_url = apk_assets[0]['browser_download_url']
    apk_filename = os.path.join(output_dir, apk_assets[0]['name'])
    
    print(f"📥 Descargando APK: {apk_assets[0]['name']}")
    apk_response = requests.get(apk_url)
    apk_response.raise_for_status()
    
    with open(apk_filename, 'wb') as f:
        f.write(apk_response.content)
    
    size_mb = os.path.getsize(apk_filename) / (1024 * 1024)
    print(f"✅ APK descargado: {apk_filename} ({size_mb:.2f} MB)")
    
    return apk_filename


def extract_apk(apk_path: str, extract_dir: str) -> None:
    """
    Extrae el contenido del APK.
    
    Args:
        apk_path: Ruta al archivo APK
        extract_dir: Directorio donde extraer el contenido
    """
    print(f"📦 Extrayendo APK a: {extract_dir}")
    
    with zipfile.ZipFile(apk_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    
    # Eliminar firma anterior (META-INF)
    meta_inf = os.path.join(extract_dir, "META-INF")
    if os.path.exists(meta_inf):
        shutil.rmtree(meta_inf)
        print("🗑️  Firma anterior eliminada (META-INF)")
    
    # Contar archivos
    file_count = sum(len(files) for _, _, files in os.walk(extract_dir))
    print(f"✅ {file_count} archivos extraídos")


def find_dex_files(extract_dir: str) -> list:
    """
    Encuentra todos los archivos .dex en el directorio extraído.
    
    Args:
        extract_dir: Directorio donde se extrajo el APK
        
    Returns:
        Lista de rutas relativas a los archivos .dex
    """
    dex_files = []
    
    for root, _, files in os.walk(extract_dir):
        for file in files:
            if file.endswith('.dex'):
                full_path = os.path.join(root, file)
                # Ruta relativa desde extract_dir
                rel_path = os.path.relpath(full_path, extract_dir)
                dex_files.append(rel_path)
    
    print(f"🔍 Encontrados {len(dex_files)} archivos .dex:")
    for dex in sorted(dex_files):
        print(f"   - {dex}")
    
    return dex_files


def repackage_apk_stored(extract_dir: str, output_apk: str, dex_files: list) -> None:
    """
    Reempaqueta el APK con archivos .dex almacenados sin compresión (STORED).
    
    Este es el paso CRÍTICO para la compatibilidad con dispositivos de gama baja.
    
    Args:
        extract_dir: Directorio con el contenido extraído del APK
        output_apk: Ruta donde guardar el APK reempaquetado
        dex_files: Lista de rutas relativas a los archivos .dex
    """
    print(f"📦 Reempaquetando APK con .dex STORED: {output_apk}")
    
    # Convertir a conjunto para búsqueda rápida
    dex_set = set(dex_files)
    
    with zipfile.ZipFile(output_apk, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(extract_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, extract_dir)
                
                if arcname in dex_set:
                    # Archivos .dex: SIN compresión (STORED) - CRÍTICO
                    zipf.write(file_path, arcname, zipfile.ZIP_STORED)
                    size_kb = os.path.getsize(file_path) / 1024
                    print(f"   📄 [STORED] {arcname} ({size_kb:.1f} KB)")
                else:
                    # Otros archivos: con compresión normal
                    zipf.write(file_path, arcname, zipfile.ZIP_DEFLATED)
    
    size_mb = os.path.getsize(output_apk) / (1024 * 1024)
    print(f"✅ APK reempaquetado: {output_apk} ({size_mb:.2f} MB)")


def verify_dex_stored(apk_path: str) -> bool:
    """
    Verifica que todos los archivos .dex estén almacenados como STORED.
    
    Args:
        apk_path: Ruta al APK a verificar
        
    Returns:
        True si todos los .dex están STORED, False en caso contrario
    """
    print(f"🔍 Verificando compresión de .dex en: {apk_path}")
    
    with zipfile.ZipFile(apk_path, 'r') as zipf:
        dex_files = [info for info in zipf.infolist() if info.filename.endswith('.dex')]
        
        if not dex_files:
            print("⚠️  No se encontraron archivos .dex")
            return False
        
        all_stored = True
        for info in dex_files:
            compress_type = info.compress_type
            type_name = "STORED" if compress_type == zipfile.ZIP_STORED else "DEFLATED"
            status = "✅" if compress_type == zipfile.ZIP_STORED else "❌"
            print(f"   {status} {info.filename}: {type_name}")
            
            if compress_type != zipfile.ZIP_STORED:
                all_stored = False
        
        if all_stored:
            print("✅ Todos los archivos .dex están correctamente almacenados (STORED)")
        else:
            print("❌ ALGUNOS archivos .dex están comprimidos (DEFLATED) - ¡Esto causará crashes!")
        
        return all_stored


def create_keystore(keystore_path: str, password: str, alias: str = "mykey") -> None:
    """
    Crea un keystore para firmar el APK.
    
    Args:
        keystore_path: Ruta donde guardar el keystore
        password: Contraseña para el keystore
        alias: Alias de la clave
    """
    print(f"🔐 Creando keystore: {keystore_path}")
    
    cmd = [
        "keytool", "-genkeypair", "-v",
        "-keystore", keystore_path,
        "-alias", alias,
        "-keyalg", "RSA",
        "-keysize", "2048",
        "-validity", "10000",
        "-storepass", password,
        "-keypass", password,
        "-dname", "CN=APKOptimizer, OU=Dev, O=Optimizer, L=City, S=State, C=US"
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    print("✅ Keystore creado")


def sign_apk(input_apk: str, output_apk: str, keystore_path: str, password: str, alias: str = "mykey") -> None:
    """
    Firma el APK usando apksigner (preferido) o jarsigner (fallback).
    
    Args:
        input_apk: Ruta al APK sin firmar
        output_apk: Ruta donde guardar el APK firmado
        keystore_path: Ruta al keystore
        password: Contraseña del keystore
        alias: Alias de la clave
    """
    print(f"✍️  Firmando APK: {input_apk}")
    
    # Intentar usar apksigner primero (mejor para Android 11+)
    apksigner_path = shutil.which("apksigner")
    
    if apksigner_path:
        print("   Usando apksigner (recomendado para Android 11+)")
        
        # Primero hacer zipalign si está disponible
        zipalign_path = shutil.which("zipalign")
        aligned_apk = input_apk.replace(".apk", "-aligned.apk")
        
        if zipalign_path:
            print("   Alineando con zipalign...")
            subprocess.run(
                [zipalign_path, "-v", "-p", "4", input_apk, aligned_apk],
                check=True,
                capture_output=True
            )
            input_to_sign = aligned_apk
        else:
            input_to_sign = input_apk
        
        # Firmar con apksigner
        cmd = [
            apksigner_path, "sign",
            "--ks", keystore_path,
            "--ks-pass", f"pass:{password}",
            "--key-pass", f"pass:{password}",
            "--out", output_apk,
            input_to_sign
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Limpiar archivo alineado temporal
        if os.path.exists(aligned_apk) and aligned_apk != input_apk:
            os.remove(aligned_apk)
            
    else:
        print("   Usando jarsigner (fallback)")
        cmd = [
            "jarsigner",
            "-verbose",
            "-sigalg", "SHA256withRSA",
            "-digestalg", "SHA-256",
            "-keystore", keystore_path,
            "-storepass", password,
            "-keypass", password,
            input_apk,
            alias
        ]
        subprocess.run(cmd, check=True)
        shutil.copy(input_apk, output_apk)
    
    size_mb = os.path.getsize(output_apk) / (1024 * 1024)
    print(f"✅ APK firmado: {output_apk} ({size_mb:.2f} MB)")


def verify_apk(apk_path: str) -> None:
    """
    Verifica que el APK esté correctamente firmado y sea válido.
    
    Args:
        apk_path: Ruta al APK a verificar
    """
    print(f"🔍 Verificando APK firmado: {apk_path}")
    
    # Verificar con apksigner si está disponible
    apksigner_path = shutil.which("apksigner")
    if apksigner_path:
        try:
            result = subprocess.run(
                [apksigner_path, "verify", "-v", apk_path],
                capture_output=True,
                text=True,
                check=True
            )
            print("✅ APK verificado correctamente con apksigner")
            if "Verified using v1 scheme" in result.stdout:
                print("   ✓ Esquema v1 (JAR signing)")
            if "Verified using v2 scheme" in result.stdout:
                print("   ✓ Esquema v2 (APK Signature Scheme)")
            if "Verified using v3 scheme" in result.stdout:
                print("   ✓ Esquema v3 (APK Signature Scheme v3)")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Advertencia en verificación: {e}")
    else:
        print("   apksigner no disponible, omitiendo verificación de firma")


def main():
    parser = argparse.ArgumentParser(
        description="Optimiza APKs para dispositivos de gama baja convirtiendo .dex a STORED",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Descargar desde release y optimizar
  python optimize_apk.py --repo owner/repo --download
  
  # Optimizar APK local
  python optimize_apk.py --input mi_app.apk --output mi_app_optimized.apk
        """
    )
    
    parser.add_argument("--repo", default="manpiro12/manpiro12",
                        help="Repositorio GitHub (owner/repo)")
    parser.add_argument("--download", action="store_true",
                        help="Descargar APK desde el último release")
    parser.add_argument("--input", "-i",
                        help="Ruta al APK de entrada (si no se descarga)")
    parser.add_argument("--output", "-o", default="optimized.apk",
                        help="Ruta al APK optimizado de salida (default: optimized.apk)")
    parser.add_argument("--keystore", default="release_keystore.jks",
                        help="Ruta al keystore (default: release_keystore.jks)")
    parser.add_argument("--keystore-pass", default="android",
                        help="Contraseña del keystore (default: android)")
    parser.add_argument("--alias", default="mykey",
                        help="Alias de la clave (default: mykey)")
    parser.add_argument("--keep-temp", action="store_true",
                        help="Mantener archivos temporales")
    
    args = parser.parse_args()
    
    # Crear directorio temporal
    temp_dir = tempfile.mkdtemp(prefix="apk_opt_")
    extract_dir = os.path.join(temp_dir, "extracted")
    
    try:
        print("=" * 60)
        print("🔧 APK OPTIMIZER - Compatibilidad para gama baja")
        print("=" * 60)
        print()
        
        # Paso 1: Obtener APK
        if args.download:
            input_apk = download_apk(args.repo, temp_dir)
        elif args.input:
            input_apk = args.input
            if not os.path.exists(input_apk):
                print(f"❌ Error: No se encontró el archivo: {input_apk}")
                sys.exit(1)
        else:
            print("❌ Error: Debes especificar --download o --input")
            sys.exit(1)
        
        print()
        
        # Paso 2: Extraer APK
        os.makedirs(extract_dir)
        extract_apk(input_apk, extract_dir)
        print()
        
        # Paso 3: Encontrar archivos .dex
        dex_files = find_dex_files(extract_dir)
        if not dex_files:
            print("❌ Error: No se encontraron archivos .dex")
            sys.exit(1)
        print()
        
        # Paso 4: Reempaquetar con .dex STORED
        unsigned_apk = os.path.join(temp_dir, "unsigned.apk")
        repackage_apk_stored(extract_dir, unsigned_apk, dex_files)
        print()
        
        # Paso 5: Verificar que .dex estén STORED
        if not verify_dex_stored(unsigned_apk):
            print("❌ Error: Falló la verificación de compresión STORED")
            sys.exit(1)
        print()
        
        # Paso 6: Crear keystore
        keystore_path = os.path.join(temp_dir, args.keystore)
        create_keystore(keystore_path, args.keystore_pass, args.alias)
        print()
        
        # Paso 7: Firmar APK
        sign_apk(unsigned_apk, args.output, keystore_path, args.keystore_pass, args.alias)
        print()
        
        # Paso 8: Verificación final
        verify_apk(args.output)
        print()
        
        print("=" * 60)
        print("✅ ¡OPTIMIZACIÓN COMPLETADA!")
        print("=" * 60)
        print(f"📱 APK optimizado: {args.output}")
        print(f"📊 Tamaño final: {os.path.getsize(args.output) / (1024 * 1024):.2f} MB")
        print()
        print("💡 Este APK debería funcionar en tu Infinix Smart 8")
        print("   sin los crashes causados por .dex comprimidos.")
        print("=" * 60)
        
    finally:
        # Limpiar archivos temporales
        if not args.keep_temp and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n🧹 Archivos temporales eliminados: {temp_dir}")


if __name__ == "__main__":
    main()
