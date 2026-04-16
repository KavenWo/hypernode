export default function SparkBar({ data, color }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  return (
    <div className="mini-sparkline">
      {data.map((v, i) => {
        const h = Math.max(3, ((v - min) / (max - min + 0.01)) * 22 + 3);
        return (
          <div
            key={i}
            className="spark-bar"
            style={{
              height: h,
              background: i === data.length - 1 ? color : `${color}55`,
            }}
          />
        );
      })}
    </div>
  );
}
