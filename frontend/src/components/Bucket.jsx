import React, {useState, useEffect} from 'react';

export default function Bucket({children, isFilled, isActive }) {

    return (
        <div className={`bucket button ${isFilled} ${isActive}`}>{children }</div>
    )
}
