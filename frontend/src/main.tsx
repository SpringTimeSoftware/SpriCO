import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/global.css'

document.title = 'SpriCo AI Audit Plateform'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
