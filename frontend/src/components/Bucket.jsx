import React from 'react';

export default function Bucket(props){
    return (
        <div onClick={props.handleClick} className={`bucket ${props.isActive ? 'active' : ''} ${props.isFilled ? 'filled' : ''} ${props.isSelected ? 'selected' : ''}`}>
            <h3>Bucket {props.id}</h3>
            <p>{props.count}/<span>{props.set_value}</span></p>
        </div>
    )
}