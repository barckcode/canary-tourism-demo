/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ocean: {
          50: "#e6f4fa",
          100: "#b3dff0",
          200: "#80cae6",
          300: "#4db5dc",
          400: "#1aa0d2",
          500: "#0087b9",
          600: "#006a91",
          700: "#004d69",
          800: "#003041",
          900: "#001319",
        },
        volcanic: {
          50: "#fef3e6",
          100: "#fcddb3",
          200: "#fac780",
          300: "#f8b14d",
          400: "#f69b1a",
          500: "#dd8200",
          600: "#ab6500",
          700: "#7a4800",
          800: "#482b00",
          900: "#170e00",
        },
        tropical: {
          50: "#e8f8ee",
          100: "#b8eacc",
          200: "#88dcaa",
          300: "#58ce88",
          400: "#28c066",
          500: "#0fa74d",
          600: "#0b823b",
          700: "#085d2a",
          800: "#043819",
          900: "#011308",
        },
      },
    },
  },
  plugins: [],
};
