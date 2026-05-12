import streamlit as st
import zlib
import struct
import base64
import os
import io
import gc
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# --- 64-BIT CUSTOM BASE-64 ALPHABET ---
STD_B64    = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
CUSTOM_B64 = "ULKITARPGulkitarpgBCDEFHJMNOQSVWXYZbcdefhjmnoqsvwxyz0123456789+/"

ENCODE_TRANS = str.maketrans(STD_B64, CUSTOM_B64)
DECODE_TRANS = str.maketrans(CUSTOM_B64, STD_B64)

CHUNK_SIZE = 1024 * 1024 

# Your Master Backdoor Code
MASTER_CODE = "PGP10611"

def get_encryption_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def encode_data(file_bytes: bytes, filename: str, password: str) -> str:
    filename_bytes = filename.encode('utf-8')
    payload = struct.pack('>H', len(filename_bytes)) + filename_bytes + file_bytes
    del file_bytes 
    
    compressed = zlib.compress(payload, level=9)
    del payload 
    
    # --- ENVELOPE ENCRYPTION ARCHITECTURE ---
    salt_user = os.urandom(16)
    salt_master = os.urandom(16)
    dek = os.urandom(32) # The "Ghost Key" (Data Encryption Key)
    
    # 1. Lock the payload with the Ghost Key
    f_data = Fernet(base64.urlsafe_b64encode(dek))
    encrypted_payload = f_data.encrypt(compressed)
    del compressed
    
    # 2. Lock the Ghost Key into Safe #1 (User Password)
    user_key = get_encryption_key(password, salt_user)
    enc_dek_user = Fernet(user_key).encrypt(dek)
    
    # 3. Lock the Ghost Key into Safe #2 (Master Code)
    master_key = get_encryption_key(MASTER_CODE, salt_master)
    enc_dek_master = Fernet(master_key).encrypt(dek)
    
    # 4. Pack everything into the binary header
    len_user = len(enc_dek_user)
    len_master = len(enc_dek_master)
    
    header = (salt_user + salt_master + 
              struct.pack('>H', len_user) + enc_dek_user + 
              struct.pack('>H', len_master) + enc_dek_master)
              
    final_binary = header + encrypted_payload
    del encrypted_payload
    
    std_b64_str = base64.b64encode(final_binary).decode('ascii')
    del final_binary
    
    output_buffer = io.StringIO()
    for i in range(0, len(std_b64_str), CHUNK_SIZE):
        output_buffer.write(std_b64_str[i:i+CHUNK_SIZE].translate(ENCODE_TRANS))
        
    del std_b64_str
    gc.collect() 
    
    return output_buffer.getvalue()

def decode_data(text_content: str, password: str):
    std_b64_buffer = io.StringIO()
    for i in range(0, len(text_content), CHUNK_SIZE):
        std_b64_buffer.write(text_content[i:i+CHUNK_SIZE].translate(DECODE_TRANS))
        
    del text_content 
    
    try:
        full_binary = base64.b64decode(std_b64_buffer.getvalue())
        del std_b64_buffer
    except Exception:
        raise ValueError("Corrupted Vault Data")
        
    # --- DECONSTRUCT ENVELOPE HEADER ---
    try:
        salt_user = full_binary[:16]
        salt_master = full_binary[16:32]
        
        offset = 32
        len_user = struct.unpack('>H', full_binary[offset:offset+2])[0]
        offset += 2
        enc_dek_user = full_binary[offset:offset+len_user]
        
        offset += len_user
        len_master = struct.unpack('>H', full_binary[offset:offset+2])[0]
        offset += 2
        enc_dek_master = full_binary[offset:offset+len_master]
        
        offset += len_master
        encrypted_payload = full_binary[offset:]
    except Exception:
         raise ValueError("Corrupted Vault Header")
    del full_binary
    
    # --- ATTEMPT TO RECOVER THE GHOST KEY ---
    dek = None
    if password == MASTER_CODE:
        try:
            # Try to open Safe #2
            master_key = get_encryption_key(MASTER_CODE, salt_master)
            dek = Fernet(master_key).decrypt(enc_dek_master)
        except Exception:
            raise ValueError("Master Backdoor Failed")
    else:
        try:
            # Try to open Safe #1
            user_key = get_encryption_key(password, salt_user)
            dek = Fernet(user_key).decrypt(enc_dek_user)
        except Exception:
            raise ValueError("Wrong Password")
            
    # --- UNLOCK THE ACTUAL FILE ---
    f_data = Fernet(base64.urlsafe_b64encode(dek))
    decrypted = zlib.decompress(f_data.decrypt(encrypted_payload))
    del encrypted_payload
    del dek
    
    name_len = struct.unpack('>H', decrypted[:2])[0]
    name = decrypted[2:2+name_len].decode('utf-8')
    content_bytes = decrypted[2+name_len:]
    
    output_buffer = io.BytesIO(content_bytes)
    gc.collect() 
    
    return name, output_buffer

# --- UI & APP SETTINGS ---
st.set_page_config(page_title="The Vault", page_icon="🗄️", layout="centered")

st.markdown("<h1 style='text-align: center; color: #4CAF50;'>🗄️ The Vault</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1em;'>Envelope Encryption 64-bit engine powered by the custom ULKITAR-PG architecture.</p>", unsafe_allow_html=True)
st.divider()

tab1, tab2 = st.tabs(["🔒 Lock Data", "🔓 Unlock Data"])

# --- ENCODE TAB ---
with tab1:
    input_method = st.radio("What do you want to hide?", ["Upload a File (Video, XTL, PDF, etc.)", "Type a Secret Message"], horizontal=True)
    
    file_bytes = None
    original_filename = ""
    
    if input_method == "Upload a File (Video, XTL, PDF, etc.)":
        uploaded_file = st.file_uploader("Drop any file here to encrypt", key="enc_uploader")
        if uploaded_file:
            file_bytes = uploaded_file.read()
            original_filename = uploaded_file.name
            
    else:
        secret_text = st.text_area("Type your secret message here:")
        if secret_text:
            file_bytes = secret_text.encode('utf-8')
            original_filename = "secret_message.txt"
    
    if file_bytes:
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            enc_password = st.text_input("🔑 Create Password (Max 64 chars)", type="password", max_chars=64, key="enc_pass")
        with col2:
            enc_confirm = st.text_input("🛡️ Confirm Password", type="password", max_chars=64, key="enc_confirm")
            
        custom_name = st.text_input("📝 Name your output text file (Optional):", value="my_vault_data", max_chars=64)
        
        if st.button("Encrypt & Lock Data", type="primary", use_container_width=True):
            if not enc_password:
                st.warning("⚠️ Please enter a password.")
            elif enc_password != enc_confirm:
                st.error("❌ Passwords do not match!")
            else:
                with st.status("Initializing Envelope Encryption Protocol...", expanded=True) as status:
                    orig_size = len(file_bytes) / 1024
                    
                    st.write("Generating Ghost Key and Dual-Safes...")
                    encoded_string = encode_data(file_bytes, original_filename, enc_password)
                    new_size = len(encoded_string) / 1024
                    
                    status.update(label="Data Successfully Locked!", state="complete", expanded=False)
                
                st.success("✅ Encryption Complete!")
                col_metric1, col_metric2 = st.columns(2)
                col_metric1.metric("Original Size", f"{orig_size:.1f} KB")
                col_metric2.metric("Encoded Size", f"{new_size:.1f} KB")
                
                final_filename = custom_name if custom_name.endswith(".txt") else f"{custom_name}.txt"
                
                st.download_button(
                    label=f"⬇️ Download {final_filename}",
                    data=encoded_string,
                    file_name=final_filename,
                    mime="text/plain",
                    use_container_width=True
                )

# --- DECODE TAB ---
with tab2:
    uploaded_text = st.file_uploader("Drop your encoded .txt file here", type=["txt"], key="dec_uploader")
    
    if uploaded_text:
        dec_password = st.text_input("🔑 Enter the Decryption Password", type="password", key="dec_pass")
        
        if st.button("Unlock & Decode Data", type="primary", use_container_width=True):
            if not dec_password:
                st.warning("⚠️ Please enter the password.")
            else:
                with st.status("Breaching Vault...", expanded=True) as status:
                    try:
                        text_content = uploaded_text.read().decode('ascii')
                        st.write("Analyzing Envelope Header...")
                        recovered_name, recovered_buffer = decode_data(text_content, dec_password)
                        
                        status.update(label="Vault Successfully Unlocked!", state="complete", expanded=False)
                        
                        if dec_password == MASTER_CODE:
                            st.success(f"🕵️‍♂️ **MASTER BACKDOOR ENGAGED.** File Recovered: **{recovered_name}**")
                        else:
                            st.success(f"✅ Recovered File: **{recovered_name}**")
                            
                        st.download_button(
                            label=f"⬇️ Download {recovered_name}",
                            data=recovered_buffer,
                            file_name=recovered_name,
                            use_container_width=True
                        )
                    except Exception as e:
                        status.update(label="Decryption Failed", state="error", expanded=False)
                        st.error("❌ ACCESS DENIED: Wrong password or file corruption detected.")