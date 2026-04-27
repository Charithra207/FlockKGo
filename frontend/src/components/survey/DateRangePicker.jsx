import DatePicker from 'react-datepicker'
import 'react-datepicker/dist/react-datepicker.css'

export default function DateRangePicker({ startDate, endDate, onChange }) {
  return <DatePicker selectsRange startDate={startDate} endDate={endDate} onChange={onChange} placeholderText="When are you free to travel?" className="w-full rounded-xl border p-3" />
}
