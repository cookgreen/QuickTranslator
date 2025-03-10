document.addEventListener('DOMContentLoaded', function() {
    // Tab switching functionality
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            // Remove active class from all buttons and panes
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));
            
            // Add active class to current button and corresponding pane
            this.classList.add('active');
            const tabId = this.getAttribute('data-tab');
            document.getElementById(tabId).classList.add('active');
        });
    });
    
    // File upload handling
    const fileInput = document.getElementById('srt-file');
    const fileNameDisplay = document.getElementById('file-name');
    const sourceTextArea = document.getElementById('source-text');
    
    fileInput.addEventListener('change', function(e) {
        if (this.files && this.files[0]) {
            const file = this.files[0];
            fileNameDisplay.textContent = file.name;
            
            // Read file content
            const reader = new FileReader();
            reader.onload = function(e) {
                sourceTextArea.value = e.target.result;
            };
            reader.readAsText(file);
        }
    });
    
    // Drag and drop functionality
    const dropZone = document.querySelector('.file-upload');
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropZone.classList.add('highlight');
    }
    
    function unhighlight() {
        dropZone.classList.remove('highlight');
    }
    
    dropZone.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const file = dt.files[0];
        
        if (file && file.name.endsWith('.srt')) {
            fileInput.files = dt.files;
            fileNameDisplay.textContent = file.name;
            
            const reader = new FileReader();
            reader.onload = function(e) {
                sourceTextArea.value = e.target.result;
            };
            reader.readAsText(file);
        }
    }
    
    // Language swap functionality
    const swapBtn = document.getElementById('swap-languages');
    const sourceLanguage = document.getElementById('source-language');
    const targetLanguage = document.getElementById('target-language');
    
    swapBtn.addEventListener('click', function() {
        // Don't swap if source is set to auto-detect
        if (sourceLanguage.value === 'auto') return;
        
        const temp = sourceLanguage.value;
        sourceLanguage.value = targetLanguage.value;
        targetLanguage.value = temp;
    });
    
    // Translation functionality
    const translateBtn = document.getElementById('translate-btn');
    const targetTextArea = document.getElementById('target-text');
    
    translateBtn.addEventListener('click', function() {
        const sourceText = sourceTextArea.value.trim();
        if (!sourceText) {
            alert('Please enter or upload SRT content to translate');
            return;
        }
        
        // Show loading state
        translateBtn.disabled = true;
        translateBtn.textContent = 'Translating...';
        
        // Parse SRT content
        const subtitles = parseSRT(sourceText);
        
        // In a real implementation, you would send the subtitles to DeepSeek API
        // For this demo, we'll simulate translation with a timeout
        setTimeout(() => {
            const translatedSubtitles = translateSubtitles(subtitles, sourceLanguage.value, targetLanguage.value);
            const translatedSRT = generateSRT(translatedSubtitles);
            targetTextArea.value = translatedSRT;
            
            // Reset button state
            translateBtn.disabled = false;
            translateBtn.textContent = 'Translate';
        }, 1500);
    });
    
    // Copy to clipboard functionality
    const copyBtn = document.getElementById('copy-btn');
    
    copyBtn.addEventListener('click', function() {
        targetTextArea.select();
        document.execCommand('copy');
        
        // Visual feedback
        const originalText = this.textContent;
        this.textContent = 'Copied!';
        setTimeout(() => {
            this.textContent = originalText;
        }, 2000);
    });
    
    // Download functionality
    const downloadBtn = document.getElementById('download-btn');
    
    downloadBtn.addEventListener('click', function() {
        const content = targetTextArea.value;
        if (!content) {
            alert('No translated content to download');
            return;
        }
        
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'translated.srt';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
    
    // SRT parsing function
    function parseSRT(srtContent) {
        const subtitles = [];
        const blocks = srtContent.split('\n\n');
        
        blocks.forEach(block => {
            const lines = block.trim().split('\n');
            if (lines.length >= 3) {
                const index = parseInt(lines[0]);
                const timecode = lines[1];
                const text = lines.slice(2).join('\n');
                
                subtitles.push({
                    index,
                    timecode,
                    text
                });
            }
        });
        
        return subtitles;
    }
    
    // Translation function using DeepSeek API
    async function translateSubtitles(subtitles, sourceLang, targetLang) {
        try {

            const DeepSeekAPI = await import('./api.js').then(module => module.default);
            
            // Extract text content from subtitles
            const textsToTranslate = subtitles.map((subtitle) => subtitle.text);
            
            // Translate all subtitle texts in batch
            const translatedTexts = await DeepSeekAPI.translateBatch(textsToTranslate, sourceLang, targetLang);
            
            // Map translated texts back to subtitle objects
            return subtitles.map((subtitle, index) => {
                return {
                    ...subtitle,
                    text: translatedTexts[index] || subtitle.text
                };
            });
        } catch (error) {
            // Show error to user
            alert(`Translation error: ${error.message}`);
            console.error('Translation error:', error);
            
            // Return original subtitles if translation fails
            return subtitles;
        }
    }
    
    // Generate SRT content from subtitles
    function generateSRT(subtitles) {
        console.log(subtitles)

        return subtitles.map((subtitle) => {
            return `${subtitle.index}\n${subtitle.timecode}\n${subtitle.text}`;
        }).join('\n\n');
    }
});

// Add CSS class for drag and drop highlight
document.head.insertAdjacentHTML('beforeend', `
<style>
.file-upload.highlight {
    border-color: #3498db;
    background-color: rgba(52, 152, 219, 0.1);
}
</style>
`);