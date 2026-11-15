"""Conjunto CIEGO 3 (solo las intenciones nuevas: clima y viabilidad). Escrito antes de ampliar el entrenamiento; se evalúa UNA vez."""
CIEGO3 = {
 "clima": {"es": ["que clima tiene esa zona", "como es el clima ahi", "cuanto llueve al ano en ese lugar", "que temperatura hace en promedio",
                  "hace mucho viento alli", "hiela en esa region", "cuanta radiacion solar recibe", "dime los datos climaticos del candidato"],
           "en": ["what is the climate of that zone", "what is the weather like there", "how much does it rain per year at that place",
                  "what is the average temperature", "is it very windy there", "does it freeze in that region",
                  "how much solar radiation does it get", "tell me the climate data of the candidate"]},
 "viabilidad": {"es": ["se podria construir una base en esa zona", "es viable instalarse ahi", "que tan factible es una base en ese lugar",
                       "hay factores climaticos que compliquen una base", "cual de estos lugares es mejor para vivir",
                       "puedo levantar una estacion de campo ahi", "que riesgos climaticos tiene para una base", "dime si ese sitio es habitable"],
                "en": ["could a base be built in that zone", "is it feasible to settle there", "how feasible is a base at that place",
                       "are there climate factors that complicate a base", "which of these places is best to live in",
                       "can i set up a field station there", "what climate risks does it have for a base", "tell me if that site is habitable"]},
}
