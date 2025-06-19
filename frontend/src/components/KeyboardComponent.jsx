import Keyboard from 'react-simple-keyboard';
import 'react-simple-keyboard/build/css/index.css';

export default function KeyboardComponent({handleClose, 
    handleInput, 
    value, 
    handleChange, 
    handleAdd
}) {
    return (
        <div>
            <button className='close' onClick={handleClose}>X</button>
            <div className='display'>{value}</div>

            <Keyboard 
                layout={{default:['1 2 3', '4 5 6', '7 8 9', '0 {bksp}']}}
                onChange={handleInput}
                inputName='num'
                input={value}
                className="keyboard"
                />

            <div className='keyboard-functions'>
                <button className='startBtn' onClick={handleChange}>Change</button>
                <button className='setBtn' onClick={handleAdd}>Add</button>
            </div>    
        </div>
    )
}