#!/usr/bin/env python3
"""
Script para construir y firmar el APK usando los archivos rebuild_apk.
"""

import os
import sys
import zipfile
import subprocess
import tempfile
import shutil


def create_apk_from_rebuild(rebuild_dir: str, output_apk: str) -> None:
    """
    Crea un APK desde el directorio rebuild_apk con los .dex en STORED.
    """
    print(f"📦 Creando APK desde: {rebuild_dir}")
    print(f"📱 APK de salida: {output_apk}")
    
    # Archivos .dex que deben ir en STORED (sin compresión)
    dex_files = [f"classes{i}.dex" if i > 0 else "classes.dex" for i in range(10)]
    
    with zipfile.ZipFile(output_apk, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(rebuild_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, rebuild_dir)
                
                if file in dex_files:
                    # Archivos .dex: SIN compresión (STORED) - CRÍTICO para Infinix Smart 8
                    zipf.write(file_path, arcname, zipfile.ZIP_STORED)
                    size_kb = os.path.getsize(file_path) / 1024
                    print(f"   📄 [STORED] {arcname} ({size_kb:.1f} KB)")
                else:
                    # Otros archivos: con compresión normal
                    zipf.write(file_path, arcname, zipfile.ZIP_DEFLATED)
    
    size_mb = os.path.getsize(output_apk) / (1024 * 1024)
    print(f"✅ APK creado: {output_apk} ({size_mb:.2f} MB)")


def verify_dex_stored(apk_path: str) -> bool:
    """
    Verifica que todos los archivos .dex estén almacenados como STORED.
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
            print("❌ ALGUNOS archivos .dex están comprimidos (DEFLATED)")
        
        return all_stored


def create_keystore(keystore_path: str, password: str, alias: str = "mykey") -> None:
    """
    Crea un keystore para firmar el APK.
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
        "-dname", "CN=MELLOMOD, OU=Dev, O=MELLOMOD, L=City, S=State, C=US"
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    print("✅ Keystore creado")


def sign_apk(input_apk: str, output_apk: str, keystore_path: str, password: str, alias: str = "mykey") -> None:
    """
    Firma el APK usando apksigner.
    """
    print(f"✍️  Firmando APK: {input_apk}")
    
    # Alinear con zipalign primero
    aligned_apk = input_apk.replace(".apk", "-aligned.apk")
    print("   Alineando con zipalign...")
    subprocess.run(
        ["zipalign", "-v", "-p", "4", input_apk, aligned_apk],
        check=True,
        capture_output=True
    )
    
    # Firmar con apksigner
    print("   Firmando con apksigner...")
    cmd = [
        "apksigner", "sign",
        "--ks", keystore_path,
        "--ks-pass", f"pass:{password}",
        "--key-pass", f"pass:{password}",
        "--out", output_apk,
        aligned_apk
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Limpiar archivo alineado temporal
    if os.path.exists(aligned_apk):
        os.remove(aligned_apk)
    
    size_mb = os.path.getsize(output_apk) / (1024 * 1024)
    print(f"✅ APK firmado: {output_apk} ({size_mb:.2f} MB)")


def verify_apk(apk_path: str) -> None:
    """
    Verifica que el APK esté correctamente firmado.
    """
    print(f"🔍 Verificando APK firmado: {apk_path}")
    
    result = subprocess.run(
        ["apksigner", "verify", "-v", apk_path],
        capture_output=True,
        text=True,
        check=True
    )
    print("✅ APK verificado correctamente")
    if "Verified using v1 scheme" in result.stdout:
        print("   ✓ Esquema v1 (JAR signing)")
    if "Verified using v2 scheme" in result.stdout:
        print("   ✓ Esquema v2 (APK Signature Scheme)")
    if "Verified using v3 scheme" in result.stdout:
        print("   ✓ Esquema v3 (APK Signature Scheme v3)")


def main():
    print("=" * 60)
    print("🔧 CONSTRUCTOR DE APK - MELLOMOD 8BP")
    print("=" * 60)
    print()
    
    # Directorios
    rebuild_dir = "rebuild_apk"
    output_dir = "output"
    temp_dir = tempfile.mkdtemp(prefix="apk_build_")
    
    try:
        # Crear directorio de salida si no existe
        os.makedirs(output_dir, exist_ok=True)
        
        # Paso 1: Crear APK sin firmar
        unsigned_apk = os.path.join(temp_dir, "unsigned.apk")
        create_apk_from_rebuild(rebuild_dir, unsigned_apk)
        print()
        
        # Paso 2: Verificar que .dex estén STORED
        if not verify_dex_stored(unsigned_apk):
            print("❌ Error: Falló la verificación de compresión STORED")
            sys.exit(1)
        print()
        
        # Paso 3: Crear keystore
        keystore_path = os.path.join(temp_dir, "keystore.jks")
        keystore_pass = "mellomod123"
        alias = "mellomod"
        create_keystore(keystore_path, keystore_pass, alias)
        print()
        
        # Paso 4: Firmar APK
        final_apk = os.path.join(output_dir, "MELLOMOD_8BP_final.apk")
        sign_apk(unsigned_apk, final_apk, keystore_path, keystore_pass, alias)
        print()
        
        # Paso 5: Verificación final
        verify_apk(final_apk)
        print()
        
        print("=" * 60)
        print("✅ ¡CONSTRUCCIÓN COMPLETADA!")
        print("=" * 60)
        print(f"📱 APK final: {final_apk}")
        print(f"📊 Tamaño: {os.path.getsize(final_apk) / (1024 * 1024):.2f} MB")
        print()
        print("💡 Este APK está listo para instalar en tu Infinix Smart 8")
        print("   con los fixes de compatibilidad aplicados.")
        print("=" * 60)
        
        return final_apk
        
    finally:
        # Limpiar archivos temporales
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n🧹 Archivos temporales eliminados")


if __name__ == "__main__":
    main()
