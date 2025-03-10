// DeepSeek API Service
import config from './config.js';

/**
 * DeepSeek API Service for translation
 */
const DeepSeekAPI = {
    /**
     * Translates text using the DeepSeek API
     * @param {string} text - The text to translate
     * @param {string} sourceLang - The source language code
     * @param {string} targetLang - The target language code
     * @returns {Promise<string>} - The translated text
     */
    async translateText(text, sourceLang, targetLang) {
        // Check if text is empty
        if (!text || text.trim() === '') {
            return '';
        }
        
        // Check if API key is configured
        if (config.apiKey === 'YOUR_DEEPSEEK_API_KEY') {
            throw new Error('Please configure your DeepSeek API key in config.js');
        }
        
        text = text.replace(/\r\n/g," ").replace(/\n/g, " ");

        // Prepare request data
        const requestData = {
            "messages": [
              {
                "content": "Please translate this text '" + text + "' into " + targetLang,
                "role": "user"
              }
            ],
            "model": "deepseek-chat",
            "frequency_penalty": 0,
            "max_tokens": 2048,
            "presence_penalty": 0,
            "response_format": {
              "type": "text"
            },
            "stop": null,
            "stream": false,
            "stream_options": null,
            "temperature": 1,
            "top_p": 1,
            "tools": null,
            "tool_choice": "none",
            "logprobs": false,
            "top_logprobs": null
        }

        // Set request options
        const requestOptions = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${config.apiKey}`,
            },
            body: JSON.stringify(requestData),
        };
        
        // Implement retry logic
        let retries = 0;
        let lastError = null;
        
        while (retries <= config.maxRetries) {
            try {
                // Make API request with timeout
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), config.timeout);
                
                if (config.debug && retries > 0) {
                    console.log(`DeepSeek API retry attempt ${retries}/${config.maxRetries}`);
                }
                
                const response = await fetch(config.apiEndpoint, {
                    ...requestOptions,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);

                // Handle HTTP errors
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.message || `API request failed with status ${response.status}`);
                }

                var promised_response = response.json();

                // Parse response
                const data = await promised_response.then(deepseek_ret => {
                    return deepseek_ret;
                });
                
                if (config.debug) {
                    console.log('DeepSeek API Response:', data);
                }

                return data.choices[0].message.content || '';
            } catch (error) {
                lastError = error;
                
                if (error.name === 'AbortError') {
                    console.error(`Request timed out after ${config.timeout}ms, retry ${retries}/${config.maxRetries}`);
                } else {
                    console.error(`DeepSeek API Error: ${error.message}, retry ${retries}/${config.maxRetries}`);
                }
                
                // If we've reached max retries or the error is not retryable, throw it
                if (retries >= config.maxRetries || 
                    // Don't retry if it's a configuration error
                    error.message.includes('configure your DeepSeek API key')) {
                    throw lastError;
                }
                
                // Wait before retrying (exponential backoff)
                const delay = Math.min(1000 * Math.pow(2, retries), 10000);
                await new Promise(resolve => setTimeout(resolve, delay));
                retries++;
            }
        }
        
        // This should never be reached due to the throw in the loop, but just in case
        throw lastError;
    },

    /**
     * Translates a batch of texts using the DeepSeek API
     * @param {Array<string>} texts - Array of texts to translate
     * @param {string} sourceLang - The source language code
     * @param {string} targetLang - The target language code
     * @returns {Promise<Array<string>>} - Array of translated texts
     */
    async translateBatch(texts, sourceLang, targetLang) {
        try {
            // For small batches, we can translate them in parallel
            if (texts.length <= 5) {
                const promises = texts.map(text => 
                    this.translateText(text, sourceLang, targetLang)
                );
                return await Promise.all(promises);
            }
            
            // For larger batches, translate sequentially to avoid rate limits
            const results = [];
            for (const text of texts) {
                const translated = await this.translateText(text, sourceLang, targetLang);
                results.push(translated);
            }
            return results;
        } catch (error) {
            console.error('Batch translation error:', error);
            throw error;
        }
    }
};

export default DeepSeekAPI;