// improved-encryption-utils.js
class ChatEncryption {
  constructor() {
    this.keyPair = null;
    this.publicKeys = {}; // Store other users' public keys
  }

  // Generate a new key pair for the current user
  async generateKeyPair() {
    try {
      this.keyPair = await window.crypto.subtle.generateKey(
        {
          name: "RSA-OAEP",
          modulusLength: 2048,
          publicExponent: new Uint8Array([1, 0, 1]),
          hash: "SHA-256",
        },
        true, // extractable
        ["encrypt", "decrypt"]
      );
      return this.exportPublicKey(this.keyPair.publicKey);
    } catch (error) {
      console.error("Error generating key pair:", error);
      throw error;
    }
  }

  // Export public key for sharing
  async exportPublicKey(publicKey) {
    try {
      const exported = await window.crypto.subtle.exportKey("spki", publicKey);
      return this._arrayBufferToBase64(exported);
    } catch (error) {
      console.error("Error exporting public key:", error);
      throw error;
    }
  }

  // Import someone else's public key
  async importPublicKey(base64Key) {
    try {
      const keyBuffer = this._base64ToArrayBuffer(base64Key);
      return await window.crypto.subtle.importKey(
        "spki",
        keyBuffer,
        {
          name: "RSA-OAEP",
          hash: "SHA-256",
        },
        true,
        ["encrypt"]
      );
    } catch (error) {
      console.error("Error importing public key:", error);
      throw error;
    }
  }

  // Store a user's public key
  async addUserPublicKey(userId, base64PublicKey) {
    try {
      this.publicKeys[userId] = await this.importPublicKey(base64PublicKey);
      console.log(`Successfully added public key for user ${userId}`);
      return true;
    } catch (error) {
      console.error(`Error adding public key for user ${userId}:`, error);
      return false;
    }
  }

  // Generate a random AES key for hybrid encryption
  async generateAESKey() {
    return await window.crypto.subtle.generateKey(
      {
        name: "AES-GCM",
        length: 256
      },
      true,
      ["encrypt", "decrypt"]
    );
  }

  // Export AES key to raw format
  async exportAESKey(key) {
    const exported = await window.crypto.subtle.exportKey("raw", key);
    return new Uint8Array(exported);
  }

  // Import AES key from raw format
  async importAESKey(keyData) {
    return await window.crypto.subtle.importKey(
      "raw",
      keyData,
      {
        name: "AES-GCM",
        length: 256
      },
      false,
      ["encrypt", "decrypt"]
    );
  }

  // Encrypt a message using hybrid encryption (AES + RSA)
  async encryptMessage(message, userId) {
    try {
      console.log(`Starting encryption for user ${userId}`);
      
      // Check if we have the public key for this user
      if (!this.publicKeys[userId]) {
        console.error(`No public key found for user ${userId}`);
        throw new Error(`No public key found for user ${userId}`);
      }

      // Generate a random AES key
      const aesKey = await this.generateAESKey();
      console.log("Generated AES key for message encryption");
      
      // Generate a random IV
      const iv = window.crypto.getRandomValues(new Uint8Array(12));
      
      // Encrypt the message with AES-GCM
      const encodedMessage = new TextEncoder().encode(message);
      const encryptedContent = await window.crypto.subtle.encrypt(
        {
          name: "AES-GCM",
          iv: iv
        },
        aesKey,
        encodedMessage
      );
      
      // Export the AES key
      const rawAesKey = await this.exportAESKey(aesKey);
      
      // Encrypt the AES key with the user's public RSA key
      const encryptedKey = await window.crypto.subtle.encrypt(
        {
          name: "RSA-OAEP"
        },
        this.publicKeys[userId],
        rawAesKey
      );
      
      // Combine everything into a package
      const result = {
        iv: this._arrayBufferToBase64(iv),
        encryptedKey: this._arrayBufferToBase64(encryptedKey),
        encryptedContent: this._arrayBufferToBase64(encryptedContent)
      };
      
      console.log(`Encryption successful for user ${userId}`);
      return JSON.stringify(result);
    } catch (error) {
      console.error(`Error encrypting message for ${userId}:`, error);
      throw error;
    }
  }

  // Decrypt a message using hybrid encryption
  async decryptMessage(encryptedData) {
    try {
      if (!this.keyPair) {
        throw new Error("No private key available for decryption");
      }
      
      const encryptedPackage = JSON.parse(encryptedData);
      
      // Extract components
      const iv = this._base64ToArrayBuffer(encryptedPackage.iv);
      const encryptedKey = this._base64ToArrayBuffer(encryptedPackage.encryptedKey);
      const encryptedContent = this._base64ToArrayBuffer(encryptedPackage.encryptedContent);
      
      // Decrypt the AES key with the private RSA key
      const rawAesKey = await window.crypto.subtle.decrypt(
        {
          name: "RSA-OAEP"
        },
        this.keyPair.privateKey,
        encryptedKey
      );
      
      // Import the AES key
      const aesKey = await this.importAESKey(rawAesKey);
      
      // Decrypt the message content
      const decryptedContent = await window.crypto.subtle.decrypt(
        {
          name: "AES-GCM",
          iv: iv
        },
        aesKey,
        encryptedContent
      );
      
      return new TextDecoder().decode(decryptedContent);
    } catch (error) {
      console.error("Error decrypting message:", error);
      return "[Decryption failed]";
    }
  }

  // Helper: Convert ArrayBuffer to Base64 string
  _arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }

  // Helper: Convert Base64 string to ArrayBuffer
  _base64ToArrayBuffer(base64) {
    const binaryString = window.atob(base64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  }
}

// Export the class
window.ChatEncryption = ChatEncryption;