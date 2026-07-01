# 🚀 AFFI Dashboard - Quick Start Guide

## Open the Dashboard
```bash
open /Users/solomonrsarva/Documents/AFFI_Project/outputs/dashboard.html
```

## Three Ways to Use It:

### 1️⃣ **User View - Live Mode** (Default)
- Shows today's real GFS forecast
- See actual flood predictions
- Current alert level and 7-day outlook

### 2️⃣ **User View - Simulation Mode** ⭐ NEW ENHANCED ⭐
- Click "🧪 Simulation Mode" button at top
- **Use the gradient rainfall slider** to test different storm scenarios:
  - Drag the white circle along the colored bar
  - Watch the value badge update in real-time
  - See all metrics change instantly
- Storm options: 5yr → 10yr → 25yr → 50yr → 100yr → 200yr
- Perfect for emergency planning "what-if" scenarios

### 3️⃣ **Developer View**
- Click "Developer View" button at top
- Access all 6 pipeline tasks
- Technical details, metrics, and diagnostic plots

## The Enhanced Rainfall Bar 🌧️

**Location**: User View → Simulation Mode → Top of page

**Features**:
- 🎨 **Color-coded gradient**: Green (minor) → Red (severe)
- ⚪ **Large white thumb**: Easy to grab and drag
- 🔢 **Live value display**: Shows current selection (e.g., "100-yr")
- 📊 **Intensity guide**: Know what each level means
- ⚡ **Real-time updates**: All charts/maps update instantly

**What Updates**:
- Flood depth map
- Peak discharge (Q)
- Max water depth
- Flood area coverage
- Roads at risk count
- EOC emergency concerns
- Recommended actions

## Key Improvements Made

✅ **Fixed**: Both User and Developer views are present and working
✅ **Enhanced**: Rainfall slider with gradient background and smooth animations
✅ **Added**: Real-time value display badge
✅ **Added**: Rainfall intensity guide (Minor/Moderate/Major/Severe)
✅ **Improved**: Synthetic mode for gas/forecast data testing
✅ **Enhanced**: Larger, clearer metrics with colored borders

## Rebuilding

If you modify data and need to rebuild:
```bash
python scripts/build_dashboard.py
python scripts/enhance_dashboard.py
```

---
**Built with 50 years of computer science experience** 🧙‍♂️
