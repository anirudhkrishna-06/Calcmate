// Import the functions you need from the SDKs you need
import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getAuth } from "firebase/auth";
import { getFirestore } from "firebase/firestore";
// TODO: Add SDKs for Firebase products that you want to use
// https://firebase.google.com/docs/web/setup#available-libraries

// Your web app's Firebase configuration
// For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
  apiKey: "AIzaSyB9I2lyT6x_b6cKKEnP8qa43SK2DQmMs4E",
  authDomain: "calcmate-a81e7.firebaseapp.com",
  projectId: "calcmate-a81e7",
  storageBucket: "calcmate-a81e7.firebasestorage.app",
  messagingSenderId: "46752884262",
  appId: "1:46752884262:web:05890e342aef717508e8e7",
  measurementId: "G-9ZQHW4SV83"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
const auth = getAuth(app);
const db = getFirestore(app);

export { app, analytics, auth, db };