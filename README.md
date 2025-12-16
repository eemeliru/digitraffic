# Digitraffic Custom Component for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![hacs][hacsbadge]][hacs]

**Integration is in early development phase and everything is subject to change.**

A Home Assistant custom integration that provides real-time traffic information from Finland's [Digitraffic](https://www.digitraffic.fi/) service. Monitor traffic messages and weather cameras directly from your Home Assistant dashboard.

> **Note**: This is an unofficial community-developed integration and is not affiliated with or endorsed by Digitraffic or Fintraffic.

## Features

### Traffic Messages 
Real-time traffic announcements, road works, weight restrictions, and exempted transport notifications.
- **Municipality Filtering**: Filter traffic messages by specific Finnish municipalities.
- **Situation Type Filtering**: Choose which types of traffic events to monitor.
- **Dynamic Entity Management**: Traffic message sensors are automatically created and removed as incidents appear and clear.

### Weather Cameras 
Live _(refreshing every 10mins)_ road weather camera images from across Finland.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add `https://github.com/eemeliru/digitraffic` as repository and select "Integration" as category
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/digitraffic` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

_YAML configuration isn't tested or supported._

### UI

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Digitraffic"
4. Choose the service type:
   - **Traffic Messages**: Monitor road traffic incidents and announcements
   - **Weathercams**: View live road camera images

#### Traffic Messages Setup

1. **Select municipalities**: Choose one or more municipalities to monitor, or leave empty to monitor all of Finland
2. **Select situation types**: Choose which types of incidents to track:
   - Traffic Announcements
   - Road Works
   - Weight Restrictions
   - Exempted Transports

#### Weather Camera Setup

1. **Select municipality**: Choose municipality where wanted weather camera is located.
2. **Select wanted location**: Choose from available road weather cameras in selected municipality.
3. **Select camera view**: Choose one or more camera views from available options.
4. The camera entity/entities will provide live images updated every 10 minutes.

## Usage Examples

Check out the [`examples/`](examples/) folder for practical examples on how to use this integration:

- **automation-notifications.yaml**: Example automations for traffic incident notifications
- **map-card-example.yaml**: Example dashboard card configuration for displaying traffic data on a map

These examples will help you get started with setting up automations and visualizations for your traffic data.

## Data Attribution

Data provided by Fintraffic / digitraffic.fi under CC 4.0 BY license.

*Liikennetietojen lähde Fintraffic / digitraffic.fi, lisenssi CC 4.0 BY*


## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Support

- [Report issues][issues]
- [Request features][issues]
- [Ask questions in Discussions](https://github.com/eemeliru/digitraffic/discussions)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

[releases-shield]: https://img.shields.io/github/release/eemeliru/digitraffic.svg
[releases]: https://github.com/eemeliru/digitraffic/releases
[license-shield]: https://img.shields.io/github/license/eemeliru/digitraffic.svg
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[issues]: https://github.com/eemeliru/digitraffic/issues
