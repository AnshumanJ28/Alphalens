#pragma once
#include <string>
#include <fstream>
#include <filesystem>
#include <chrono>
#include <iostream>
namespace fs = std::filesystem;
namespace cache {
    constexpr int IST_OFFSET_SECONDS = 19800; // UTC+5:30
    constexpr int MARKET_OPEN_HOUR = 9;       // 9:00 AM IST

    inline std::string cache_dir(const std::string& ticker) {
        std::string dir = "cache/" + ticker;
        fs::create_directories(dir);
        return dir;
    }
    inline std::string cache_path(const std::string& ticker, const std::string& key) {
        return cache_dir(ticker) + "/" + key + ".json";
    }

    // Returns the Unix timestamp of the most recent 9:00 AM IST boundary.
    // If it is currently before 9:00 AM IST, this returns yesterday's 9:00 AM.
    inline long long last_market_open_epoch() {
        auto now = std::chrono::system_clock::now();
        auto epoch = std::chrono::duration_cast<std::chrono::seconds>(now.time_since_epoch()).count();
        long long ist_epoch = epoch + IST_OFFSET_SECONDS;
        long long ist_day_start = (ist_epoch / 86400) * 86400;          // midnight IST
        long long ist_9am = ist_day_start + (MARKET_OPEN_HOUR * 3600);  // 9:00 AM IST
        if (ist_epoch < ist_9am) {
            ist_9am -= 86400; // before 9 AM today, use yesterday's 9 AM
        }
        return ist_9am - IST_OFFSET_SECONDS; // convert back to UTC epoch
    }

    inline bool is_cache_valid(const std::string& path) {
        if (!fs::exists(path)) return false;
        auto last_write = fs::last_write_time(path);
        
        // C++17 compatible conversion from file_time_type to Unix epoch
        auto ftime_now = fs::file_time_type::clock::now();
        auto stime_now = std::chrono::system_clock::now();
        auto diff = stime_now.time_since_epoch() - ftime_now.time_since_epoch();
        
        auto file_epoch = std::chrono::duration_cast<std::chrono::seconds>(last_write.time_since_epoch() + diff).count();
        return file_epoch >= last_market_open_epoch();
    }
    inline std::string read_cache(const std::string& path) {
        std::ifstream f(path);
        if (!f.is_open()) return "";
        std::string content((std::istreambuf_iterator<char>(f)),
                             std::istreambuf_iterator<char>());
        return content;
    }
    inline void write_cache(const std::string& path, const std::string& content) {
        fs::path p(path);
        if (p.has_parent_path()) {
            fs::create_directories(p.parent_path());
        }
        std::ofstream f(path);
        if (f.is_open()) {
            f << content;
        }
    }
    inline bool has_valid_unified_cache(const std::string& ticker) {
        return is_cache_valid(cache_path(ticker, "unified_fetch"));
    }
} 
