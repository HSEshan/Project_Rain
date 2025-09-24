interface CardProps {
  title: string;
  image: React.ReactNode;
  onClick: () => void;
}

export default function Card({ title, image, onClick }: CardProps) {
  return (
    <div
      className="w-60 h-72 text-white rounded-md p-4 flex flex-col items-center 
      justify-center gap-4 border-2 border-white cursor-pointer hover:border-blue-500 transition-all duration-300"
      onClick={onClick}
    >
      <h1 className="text-2xl text-white font-bold">{title}</h1>
      {image}
    </div>
  );
}
