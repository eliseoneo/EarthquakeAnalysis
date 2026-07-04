import cdsapi

client = cdsapi.Client()

client.retrieve(
    "reanalysis-era5-single-levels",
    {
        "product_type": "reanalysis",
        "variable": [
            "mean_sea_level_pressure",
            "total_precipitation",
            "2m_temperature",
            "volumetric_soil_water_layer_1"
        ],
        "year": "2026",
        "month": "06",
        "day": ["24", "25", "26"],
        "time": [f"{h:02d}:00" for h in range(24)],
        "area": [15, -75, 0, -55],
        "format": "netcdf"
    },
    "era5_venezuela_20260624_20260626.nc"
)
