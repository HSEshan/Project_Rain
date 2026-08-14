interface CardProps {
  title: string;
  image: React.ReactNode;
  onClick: () => void;
  /** Rendered as a count bubble; hidden when zero or undefined. */
  badge?: number;
}

export default function Card({ title, image, onClick, badge }: CardProps) {
  return (
    <div
      className="relative w-60 h-72 text-white rounded-md p-4 flex flex-col items-center
      justify-center gap-4 border-2 border-white cursor-pointer hover:border-blue-500 transition-all duration-300"
      onClick={onClick}
    >
      {!!badge && (
        <span className="absolute top-3 right-3 min-w-6 h-6 px-2 flex items-center justify-center text-sm font-bold bg-red-500 rounded-full">
          {badge}
        </span>
      )}
      <h1 className="text-2xl text-white font-bold">{title}</h1>
      {image}
    </div>
  );
}
