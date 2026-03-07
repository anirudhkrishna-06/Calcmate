# Math Problem Solver - React Frontend

A modern, ChatGPT-like React frontend for your math problem-solving chatbot with text input and image upload (OCR) capabilities.

## Features

✅ **Text Chat Interface** - Type math questions and get instant answers
✅ **Image Upload & OCR** - Upload images of math problems that get converted to text
✅ **Real-time Chat** - ChatGPT-style conversation interface
✅ **Responsive Design** - Works on desktop, tablet, and mobile
✅ **Loading States** - Visual feedback during processing
✅ **Auto-scroll** - Automatically scrolls to latest messages
✅ **Image Preview** - Preview uploaded images before processing

## Project Structure

```
math-chatbot-frontend/
├── public/
│   └── index.html
├── src/
│   ├── App.js
│   ├── index.js
│   ├── index.css
│   └── MathChatbot.jsx (main component)
├── package.json
├── tailwind.config.js
└── postcss.config.js
```

## Installation & Setup

### 1. Create React App Structure

```bash
# Create a new directory
mkdir math-chatbot-frontend
cd math-chatbot-frontend

# Create src directory
mkdir src public
```

### 2. Copy Files

Copy all the provided files to their respective locations:
- Move `App.js`, `index.js`, `index.css`, `MathChatbot.jsx` to `src/` folder
- Move `index.html` to `public/` folder
- Keep `package.json`, `tailwind.config.js`, `postcss.config.js` in root

### 3. Install Dependencies

```bash
npm install
```

This will install:
- React & React DOM
- Tailwind CSS (for styling)
- Lucide React (for icons)
- React Scripts (development tools)

### 4. Configure Backend API Endpoints

Open `src/MathChatbot.jsx` and update the API endpoints with your actual backend URLs:

#### OCR Endpoint (Line ~47):
```javascript
const response = await fetch('YOUR_BACKEND_URL/ocr', {
  method: 'POST',
  body: formData,
});
```

Replace `'YOUR_BACKEND_URL/ocr'` with your actual OCR endpoint, for example:
```javascript
const response = await fetch('http://localhost:5000/api/ocr', {
```

#### Expected OCR Response Format:
```json
{
  "extractedText": "solve x^2 + 5x + 6 = 0",
  // OR
  "text": "solve x^2 + 5x + 6 = 0"
}
```

#### Chat Endpoint (Line ~75):
```javascript
const response = await fetch('YOUR_BACKEND_URL/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    question: userMessage.content,
  }),
});
```

Replace `'YOUR_BACKEND_URL/chat'` with your actual chatbot endpoint, for example:
```javascript
const response = await fetch('http://localhost:5000/api/chat', {
```

#### Expected Chat Response Format:
```json
{
  "answer": "The solution is x = -2 or x = -3",
  // OR
  "response": "The solution is x = -2 or x = -3"
}
```

### 5. Run the Application

```bash
npm start
```

The app will open at `http://localhost:3000`

## Backend Integration Guide

### Your Backend Should Have Two Endpoints:

#### 1. OCR Endpoint
- **Method:** POST
- **Content-Type:** multipart/form-data
- **Request Body:** Form data with `image` field containing the uploaded file
- **Response:** JSON with `extractedText` or `text` field

Example Python (Flask):
```python
@app.route('/api/ocr', methods=['POST'])
def ocr():
    image = request.files['image']
    # Your OCR processing logic here
    extracted_text = process_image(image)
    return jsonify({'extractedText': extracted_text})
```

#### 2. Chat Endpoint
- **Method:** POST
- **Content-Type:** application/json
- **Request Body:** JSON with `question` field
- **Response:** JSON with `answer` or `response` field

Example Python (Flask):
```python
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    question = data['question']
    # Your chatbot logic here
    answer = solve_math_problem(question)
    return jsonify({'answer': answer})
```

### CORS Configuration (Important!)

Your backend needs to allow CORS requests from the React app:

```python
# Python Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
```

Or for specific origins:
```python
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})
```

## Workflow

1. **Text Input Only:**
   - User types a math question
   - Clicks send or presses Enter
   - Question sent to `/chat` endpoint
   - Answer displayed in chat

2. **Image Upload:**
   - User clicks image upload button
   - Selects an image file
   - Image sent to `/ocr` endpoint
   - Extracted text populated in input field
   - User can edit if needed
   - User clicks send
   - Question sent to `/chat` endpoint
   - Answer displayed in chat

## Customization

### Change Colors
Edit `src/MathChatbot.jsx` and modify the Tailwind classes:
- User messages: `bg-blue-600` (line ~121)
- Bot messages: `bg-white` (line ~123)
- Send button: `bg-blue-600` (line ~203)

### Change Placeholder Text
Line ~192:
```javascript
placeholder="Type your math question here..."
```

### Add Authentication
Add headers to fetch requests:
```javascript
const response = await fetch('YOUR_BACKEND_URL/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${yourAuthToken}`
  },
  body: JSON.stringify({
    question: userMessage.content,
  }),
});
```

## Build for Production

```bash
npm run build
```

This creates an optimized production build in the `build/` folder.

## Troubleshooting

### CORS Errors
- Ensure your backend has CORS enabled
- Check that the API URLs are correct

### Images Not Uploading
- Verify the backend accepts `multipart/form-data`
- Check the field name is `'image'` in your backend

### Messages Not Sending
- Open browser console (F12) to see errors
- Verify backend endpoints are running
- Check request/response formats match

## Tech Stack

- **React 18** - UI framework
- **Tailwind CSS** - Styling
- **Lucide React** - Icons
- **Fetch API** - HTTP requests

## License

MIT

## Support

For issues or questions, check:
1. Browser console for errors (F12)
2. Network tab to inspect API calls
3. Backend logs for server-side errors

---

Happy coding! 🚀
