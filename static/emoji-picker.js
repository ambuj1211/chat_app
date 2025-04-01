// emoji-picker.js
const emojiList = [
    "😀", "😃", "😄", "😁", "😆", "😅", "😂", "🤣", "😊", "😇",
    "🙂", "🙃", "😉", "😌", "😍", "🥰", "😘", "😗", "😙", "😚",
    "😋", "😛", "😝", "😜", "🤪", "🤨", "🧐", "🤓", "😎", "🤩",
    "😏", "😒", "😞", "😔", "😟", "😕", "🙁", "☹️", "😣", "😖",
    "😫", "😩", "🥺", "😢", "😭", "😤", "😠", "😡", "🤬", "🤯",
    "😳", "🥵", "🥶", "😱", "😨", "😰", "😥", "😓", "🤗", "🤔",
    "🤭", "🤫", "🤥", "😶", "😐", "😑", "😬", "🙄", "😯", "😦",
    "👋", "🤚", "✋", "🖐️", "👌", "✌️", "🤞", "🤟", "🤘", "🤙",
    "👍", "👎", "👊", "✊", "🤛", "🤜", "👏", "🙌", "👐", "🤲",
    "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "💔", "❣️", "💕"
];

class EmojiPicker {
    constructor(buttonElement, targetElement) {
        this.button = buttonElement;
        this.target = targetElement;
        this.pickerContainer = null;
        this.isOpen = false;
        
        this.init();
    }
    
    init() {
        this.createPickerElement();
        this.setupEventListeners();
    }
    
    createPickerElement() {
        // Create the container
        this.pickerContainer = document.createElement('div');
        this.pickerContainer.className = 'custom-emoji-picker';
        this.pickerContainer.style.display = 'none';
        
        // Create the grid for emojis
        const emojiGrid = document.createElement('div');
        emojiGrid.className = 'emoji-grid';
        
        // Add all emojis to the grid
        emojiList.forEach(emoji => {
            const emojiButton = document.createElement('button');
            emojiButton.className = 'emoji-button';
            emojiButton.textContent = emoji;
            emojiButton.addEventListener('click', () => this.insertEmoji(emoji));
            emojiGrid.appendChild(emojiButton);
        });
        
        this.pickerContainer.appendChild(emojiGrid);
        document.body.appendChild(this.pickerContainer);
    }
    
    setupEventListeners() {
        // Toggle picker when button is clicked
        this.button.addEventListener('click', (e) => {
            e.preventDefault();
            this.togglePicker();
        });
        
        // Close picker when clicking outside
        document.addEventListener('click', (e) => {
            if (this.isOpen && e.target !== this.button && !this.pickerContainer.contains(e.target)) {
                this.closePicker();
            }
        });
    }
    
    togglePicker() {
        if (this.isOpen) {
            this.closePicker();
        } else {
            this.openPicker();
        }
    }
    
    openPicker() {
        if (!this.isOpen) {
            // Position the picker near the button
            const buttonRect = this.button.getBoundingClientRect();
            this.pickerContainer.style.position = 'absolute';
            this.pickerContainer.style.top = `${buttonRect.bottom + window.scrollY}px`;
            this.pickerContainer.style.left = `${buttonRect.left + window.scrollX}px`;
            
            this.pickerContainer.style.display = 'block';
            this.isOpen = true;
        }
    }
    
    closePicker() {
        if (this.isOpen) {
            this.pickerContainer.style.display = 'none';
            this.isOpen = false;
        }
    }
    
    insertEmoji(emoji) {
        // Insert the emoji at cursor position or append to end
        if (this.target.tagName.toLowerCase() === 'textarea' || this.target.tagName.toLowerCase() === 'input') {
            const start = this.target.selectionStart;
            const end = this.target.selectionEnd;
            const text = this.target.value;
            const before = text.substring(0, start);
            const after = text.substring(end, text.length);
            this.target.value = before + emoji + after;
            this.target.selectionStart = this.target.selectionEnd = start + emoji.length;
            this.target.focus();
        }
        
        this.closePicker();
    }
}

// Export the class
window.EmojiPicker = EmojiPicker;