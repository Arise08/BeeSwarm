// Interactive Content Editor
class ContentEditor {
    constructor() {
        this.canvas = document.getElementById('canvas');
        this.selectedElement = null;
        this.elementCounter = 0;
        this.isDragging = false;
        this.dragOffset = { x: 0, y: 0 };
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupCanvas();
    }

    setupEventListeners() {
        // Toolbar buttons
        document.getElementById('addTextBtn').addEventListener('click', () => this.addTextElement());
        document.getElementById('addImageBtn').addEventListener('click', () => this.addImageElement());
        document.getElementById('addShapeBtn').addEventListener('click', () => this.addShapeElement());
        document.getElementById('clearBtn').addEventListener('click', () => this.clearCanvas());
        document.getElementById('exportBtn').addEventListener('click', () => this.exportCanvas());
        document.getElementById('closePanelBtn').addEventListener('click', () => this.closePropertiesPanel());
        
        // Image input
        document.getElementById('imageInput').addEventListener('change', (e) => this.handleImageUpload(e));
        
        // Canvas click to deselect
        this.canvas.addEventListener('click', (e) => {
            if (e.target === this.canvas || e.target.classList.contains('canvas-placeholder')) {
                this.deselectElement();
            }
        });
    }

    setupCanvas() {
        // Remove placeholder if elements exist
        const placeholder = this.canvas.querySelector('.canvas-placeholder');
        if (placeholder && this.canvas.children.length > 1) {
            placeholder.remove();
        }
    }

    addTextElement() {
        const textElement = document.createElement('div');
        textElement.className = 'draggable-element text-element';
        textElement.contentEditable = true;
        textElement.textContent = 'Double click to edit text';
        textElement.style.left = '50px';
        textElement.style.top = '50px';
        textElement.dataset.id = `element-${this.elementCounter++}`;
        textElement.dataset.type = 'text';
        
        this.setupElementEvents(textElement);
        this.canvas.appendChild(textElement);
        this.selectElement(textElement);
        this.setupCanvas();
        
        // Focus and select text
        setTimeout(() => {
            textElement.focus();
            const range = document.createRange();
            range.selectNodeContents(textElement);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
        }, 100);
    }

    addImageElement() {
        document.getElementById('imageInput').click();
    }

    handleImageUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            const imgContainer = document.createElement('div');
            imgContainer.className = 'draggable-element image-element';
            imgContainer.style.left = '50px';
            imgContainer.style.top = '50px';
            imgContainer.dataset.id = `element-${this.elementCounter++}`;
            imgContainer.dataset.type = 'image';
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.style.maxWidth = '300px';
            img.style.maxHeight = '300px';
            
            imgContainer.appendChild(img);
            this.setupElementEvents(imgContainer);
            this.canvas.appendChild(imgContainer);
            this.selectElement(imgContainer);
            this.setupCanvas();
        };
        reader.readAsDataURL(file);
        
        // Reset input
        event.target.value = '';
    }

    addShapeElement() {
        const shapeElement = document.createElement('div');
        shapeElement.className = 'draggable-element shape-element';
        shapeElement.textContent = 'Shape';
        shapeElement.style.left = '50px';
        shapeElement.style.top = '50px';
        shapeElement.style.width = '150px';
        shapeElement.style.height = '100px';
        shapeElement.dataset.id = `element-${this.elementCounter++}`;
        shapeElement.dataset.type = 'shape';
        
        this.setupElementEvents(shapeElement);
        this.canvas.appendChild(shapeElement);
        this.selectElement(shapeElement);
        this.setupCanvas();
    }

    setupElementEvents(element) {
        // Click to select
        element.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectElement(element);
        });

        // Drag functionality
        element.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('delete-btn')) return;
            
            this.isDragging = true;
            element.classList.add('dragging');
            
            const rect = element.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            
            this.dragOffset.x = e.clientX - rect.left;
            this.dragOffset.y = e.clientY - rect.top;
            
            // Prevent text selection during drag
            e.preventDefault();
        });

        // Delete button
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.textContent = '×';
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.deleteElement(element);
        });
        element.appendChild(deleteBtn);
    }

    selectElement(element) {
        // Deselect previous
        if (this.selectedElement) {
            this.selectedElement.classList.remove('selected');
        }
        
        // Select new
        this.selectedElement = element;
        element.classList.add('selected');
        
        // Show properties panel
        this.showPropertiesPanel(element);
    }

    deselectElement() {
        if (this.selectedElement) {
            this.selectedElement.classList.remove('selected');
            this.selectedElement = null;
        }
        this.closePropertiesPanel();
    }

    deleteElement(element) {
        if (this.selectedElement === element) {
            this.deselectElement();
        }
        element.remove();
        this.setupCanvas();
    }

    showPropertiesPanel(element) {
        const panel = document.getElementById('propertiesPanel');
        const content = document.getElementById('panelContent');
        
        const type = element.dataset.type;
        let html = '';

        if (type === 'text') {
            html = `
                <div class="property-group">
                    <label>Text Content</label>
                    <textarea id="prop-text" rows="4">${element.textContent}</textarea>
                </div>
                <div class="property-group">
                    <label>Font Size</label>
                    <input type="range" id="prop-fontSize" min="12" max="72" value="${parseInt(getComputedStyle(element).fontSize)}">
                    <span class="range-value" id="fontSizeValue">${parseInt(getComputedStyle(element).fontSize)}px</span>
                </div>
                <div class="property-group">
                    <label>Text Color</label>
                    <input type="color" id="prop-color" value="${this.rgbToHex(getComputedStyle(element).color)}">
                </div>
                <div class="property-group">
                    <label>Font Weight</label>
                    <select id="prop-fontWeight">
                        <option value="normal" ${getComputedStyle(element).fontWeight === 'normal' ? 'selected' : ''}>Normal</option>
                        <option value="bold" ${getComputedStyle(element).fontWeight === 'bold' ? 'selected' : ''}>Bold</option>
                    </select>
                </div>
            `;
        } else if (type === 'image') {
            const img = element.querySelector('img');
            html = `
                <div class="property-group">
                    <label>Width</label>
                    <input type="range" id="prop-width" min="50" max="800" value="${parseInt(img.style.maxWidth) || 300}">
                    <span class="range-value" id="widthValue">${parseInt(img.style.maxWidth) || 300}px</span>
                </div>
                <div class="property-group">
                    <label>Height</label>
                    <input type="range" id="prop-height" min="50" max="600" value="${parseInt(img.style.maxHeight) || 300}">
                    <span class="range-value" id="heightValue">${parseInt(img.style.maxHeight) || 300}px</span>
                </div>
                <div class="property-group">
                    <label>Opacity</label>
                    <input type="range" id="prop-opacity" min="0" max="100" value="${parseFloat(getComputedStyle(img).opacity) * 100}">
                    <span class="range-value" id="opacityValue">${Math.round(parseFloat(getComputedStyle(img).opacity) * 100)}%</span>
                </div>
            `;
        } else if (type === 'shape') {
            html = `
                <div class="property-group">
                    <label>Width</label>
                    <input type="range" id="prop-width" min="50" max="500" value="${parseInt(element.style.width) || 150}">
                    <span class="range-value" id="widthValue">${parseInt(element.style.width) || 150}px</span>
                </div>
                <div class="property-group">
                    <label>Height</label>
                    <input type="range" id="prop-height" min="50" max="500" value="${parseInt(element.style.height) || 100}">
                    <span class="range-value" id="heightValue">${parseInt(element.style.height) || 100}px</span>
                </div>
                <div class="property-group">
                    <label>Background Color</label>
                    <input type="color" id="prop-bgColor" value="${this.rgbToHex(getComputedStyle(element).backgroundImage ? '#667eea' : getComputedStyle(element).backgroundColor)}">
                </div>
                <div class="property-group">
                    <label>Border Radius</label>
                    <input type="range" id="prop-borderRadius" min="0" max="50" value="${parseInt(getComputedStyle(element).borderRadius) || 8}">
                    <span class="range-value" id="borderRadiusValue">${parseInt(getComputedStyle(element).borderRadius) || 8}px</span>
                </div>
            `;
        }

        content.innerHTML = html;
        this.setupPropertyListeners(element, type);
        panel.classList.add('open');
    }

    setupPropertyListeners(element, type) {
        if (type === 'text') {
            document.getElementById('prop-text').addEventListener('input', (e) => {
                element.textContent = e.target.value;
            });
            
            const fontSizeInput = document.getElementById('prop-fontSize');
            fontSizeInput.addEventListener('input', (e) => {
                element.style.fontSize = e.target.value + 'px';
                document.getElementById('fontSizeValue').textContent = e.target.value + 'px';
            });
            
            document.getElementById('prop-color').addEventListener('input', (e) => {
                element.style.color = e.target.value;
            });
            
            document.getElementById('prop-fontWeight').addEventListener('change', (e) => {
                element.style.fontWeight = e.target.value;
            });
        } else if (type === 'image') {
            const img = element.querySelector('img');
            
            const widthInput = document.getElementById('prop-width');
            widthInput.addEventListener('input', (e) => {
                img.style.maxWidth = e.target.value + 'px';
                document.getElementById('widthValue').textContent = e.target.value + 'px';
            });
            
            const heightInput = document.getElementById('prop-height');
            heightInput.addEventListener('input', (e) => {
                img.style.maxHeight = e.target.value + 'px';
                document.getElementById('heightValue').textContent = e.target.value + 'px';
            });
            
            const opacityInput = document.getElementById('prop-opacity');
            opacityInput.addEventListener('input', (e) => {
                img.style.opacity = e.target.value / 100;
                document.getElementById('opacityValue').textContent = e.target.value + '%';
            });
        } else if (type === 'shape') {
            const widthInput = document.getElementById('prop-width');
            widthInput.addEventListener('input', (e) => {
                element.style.width = e.target.value + 'px';
                document.getElementById('widthValue').textContent = e.target.value + 'px';
            });
            
            const heightInput = document.getElementById('prop-height');
            heightInput.addEventListener('input', (e) => {
                element.style.height = e.target.value + 'px';
                document.getElementById('heightValue').textContent = e.target.value + 'px';
            });
            
            document.getElementById('prop-bgColor').addEventListener('input', (e) => {
                element.style.background = e.target.value;
            });
            
            const borderRadiusInput = document.getElementById('prop-borderRadius');
            borderRadiusInput.addEventListener('input', (e) => {
                element.style.borderRadius = e.target.value + 'px';
                document.getElementById('borderRadiusValue').textContent = e.target.value + 'px';
            });
        }
    }

    closePropertiesPanel() {
        document.getElementById('propertiesPanel').classList.remove('open');
    }

    clearCanvas() {
        if (confirm('Are you sure you want to clear the canvas?')) {
            const elements = this.canvas.querySelectorAll('.draggable-element');
            elements.forEach(el => el.remove());
            this.selectedElement = null;
            this.closePropertiesPanel();
            this.setupCanvas();
            
            // Add placeholder back
            const placeholder = document.createElement('div');
            placeholder.className = 'canvas-placeholder';
            placeholder.textContent = 'Click "Add Text" or "Add Image" to start creating';
            this.canvas.appendChild(placeholder);
        }
    }

    exportCanvas() {
        // Create a simple export (you can enhance this to export as image)
        const elements = Array.from(this.canvas.querySelectorAll('.draggable-element'));
        const data = elements.map(el => ({
            type: el.dataset.type,
            left: el.style.left,
            top: el.style.top,
            content: el.textContent || (el.querySelector('img') ? el.querySelector('img').src : ''),
            styles: {
                fontSize: el.style.fontSize,
                color: el.style.color,
                width: el.style.width,
                height: el.style.height,
            }
        }));
        
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'canvas-export.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    rgbToHex(rgb) {
        if (rgb.startsWith('#')) return rgb;
        if (rgb.startsWith('rgb')) {
            const values = rgb.match(/\d+/g);
            if (values && values.length >= 3) {
                return '#' + values.map(v => {
                    const hex = parseInt(v).toString(16);
                    return hex.length === 1 ? '0' + hex : hex;
                }).join('');
            }
        }
        return '#000000';
    }
}

// Mouse move handler for dragging
document.addEventListener('mousemove', (e) => {
    if (window.editor && window.editor.isDragging && window.editor.selectedElement) {
        const canvasRect = window.editor.canvas.getBoundingClientRect();
        const x = e.clientX - canvasRect.left - window.editor.dragOffset.x;
        const y = e.clientY - canvasRect.top - window.editor.dragOffset.y;
        
        window.editor.selectedElement.style.left = Math.max(0, x) + 'px';
        window.editor.selectedElement.style.top = Math.max(0, y) + 'px';
    }
});

document.addEventListener('mouseup', () => {
    if (window.editor && window.editor.isDragging) {
        window.editor.isDragging = false;
        if (window.editor.selectedElement) {
            window.editor.selectedElement.classList.remove('dragging');
        }
    }
});

// Initialize editor
window.addEventListener('DOMContentLoaded', () => {
    window.editor = new ContentEditor();
});
