import React, {useState, useEffect} from 'react';

export default function Bucket({children }) {

    return (
        <h2 className='bucket button'>{children }</h2>
    )
}
