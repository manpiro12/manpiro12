import os
import requests
import zipfile
import subprocess

# Step 1: Download the APK from the latest release
def download_apk(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    response = requests.get(url)
    response.raise_for_status()
    apk_url = [asset['browser_download_url'] for asset in response.json()['assets'] if asset['name'].endswith('.apk')]
    
    if not apk_url:
        raise Exception("No APK found for download.")
    
    apk_response = requests.get(apk_url[0])
    apk_filename = apk_url[0].split('/')[-1]
    with open(apk_filename, 'wb') as apk_file:
        apk_file.write(apk_response.content)
    
    return apk_filename

# Step 2: Decompress .dex files from DEFLATED to STORED
def decompress_dex_files(apk_filename):
    with zipfile.ZipFile(apk_filename, 'r') as zip_ref:
        zip_ref.extractall("extracted_apk")

# Step 3: Repackage the APK
def repackage_apk(apk_filename):
    with zipfile.ZipFile('repackaged_' + apk_filename, 'w') as zip_ref:
        for foldername, subfolders, filenames in os.walk("extracted_apk"):
            for filename in filenames:
                file_path = os.path.join(foldername, filename)
                zip_ref.write(file_path, os.path.relpath(file_path, "extracted_apk"))

# Step 4: Create a keystore
def create_keystore():
    keystore_name = "my_keystore.jks"
    subprocess.run(["keytool", "-genkeypair", "-v", "-keystore", keystore_name,
                    "-alias", "my_alias", "-keyalg", "RSA", "-keysize", "2048",
                    "-validity", "10000", "-dname", "CN=MyName, OU=MyUnit, O=MyOrg, L=MyCity, S=MyState, C=MyCountry"],
                   check=True)

# Step 5: Sign the APK
def sign_apk(apk_filename):
    subprocess.run(["jarsigner", "-verbose", "-sigalg", "SHA1withRSA", "-digestalg", "SHA1",
                    "-keystore", "my_keystore.jks", "repackaged_" + apk_filename, "my_alias"],
                   check=True)

# Step 6: Prepare APK for upload (normally this would involve uploading to a server)
def prepare_for_upload():
    print("APK is signed and ready for upload.")

def main():
    repo = "manpiro12/manpiro12"
    apk_filename = download_apk(repo)
    decompress_dex_files(apk_filename)
    repackage_apk(apk_filename)
    create_keystore()
    sign_apk(apk_filename)
    prepare_for_upload()

if __name__ == "__main__":
    main()