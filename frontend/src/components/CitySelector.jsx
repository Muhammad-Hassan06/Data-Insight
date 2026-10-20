import React from 'react';
import { CITY_META } from '../data/mockData';

const CITIES = ['Lahore', 'Karachi', 'Islamabad', 'Peshawar'];

export default function CitySelector({ selectedCity, onCityChange }) {
  return (
    <div className="city-selector" id="city-selector">
      <div className="city-buttons">
        {CITIES.map(city => (
          <button
            key={city}
            id={`city-btn-${city.toLowerCase()}`}
            className={`city-btn ${selectedCity === city ? 'active' : ''}`}
            onClick={() => onCityChange(city)}
          >
            <span className="city-flag">{CITY_META[city]?.flag}</span>
            <span>{city}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
