import React from 'react';
import ReactDOM from 'react-dom/client';
import Converter from './pages/Converter';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <Converter />
    </React.StrictMode>,
);
