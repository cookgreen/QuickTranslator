// DeepSeek API Configuration
/**
 * Configuration for the DeepSeek Translation API
 * 
 * To use this application:
 * 1. Sign up for a DeepSeek API account at https://platform.deepseek.com
 * 2. Generate an API key from your account dashboard
 * 3. Replace 'YOUR_DEEPSEEK_API_KEY' below with your actual API key
 */
const config = {
    // Your DeepSeek API key (required)
    // Replace this with your actual API key from DeepSeek platform
    apiKey: 'YOUR_DEEPSEEK_API_KEY',
    
    // API endpoint for DeepSeek translation service
    // This should match the official DeepSeek translation API endpoint
    apiEndpoint: 'https://api.deepseek.com/v1/translate',
    
    // Default request timeout in milliseconds (30 seconds)
    timeout: 30000,
    
    // Maximum number of retries for failed requests
    maxRetries: 3,
    
    // Whether to log API requests and responses (for debugging)
    // Set to true when troubleshooting API issues
    debug: false
};

// Do not modify below this line
export default config;