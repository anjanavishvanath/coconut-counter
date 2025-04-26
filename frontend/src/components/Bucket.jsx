import React from 'react';

export default function Bucket(props){
    return (
        <div onClick={props.handleClick} className={`bucket ${props.isActive ? 'active' : ''} ${props.isFilled ? 'filled' : ''}`}>
            <h3>Bucket {props.id}</h3>
            <p>{props.count}/{props.set_value}</p>
        </div>
    )
}