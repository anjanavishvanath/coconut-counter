import Keyboard from 'react-simple-keyboard';
import 'react-simple-keyboard/build/css/index.css';

export default function KeyboardComponent({handleClose, handleInput}) {
    //inlcude onchange and inputname
    return (
        <div>
            <button className='close' onClick={handleClose}>X</button>
            <Keyboard 
                layout={{default:['1 2 3', '4 5 6', '7 8 9', '0 {bksp}']}}
                onChange={handleInput}
                />    
        </div>
    )
}