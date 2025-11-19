import React from 'react';
import ReactDOM from 'react-dom/client';
import ImageToMeshConverter from './image_to_stl_converter';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <ImageToMeshConverter />
    </React.StrictMode>,
);
