export default function TimeLogPlantSelector({ plants, activePlantId, onChange }) {
  return (
    <div className="timelog-plant">
      <label className="timelog-plant__label">식물 선택</label>
      <select
        className="timelog-plant__select"
        value={activePlantId}
        onChange={onChange}
      >
        <option value="">식물을 선택하세요</option>
        {plants.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </div>
  );
}
