use log::{info, error};
use std::time::SystemTime;
use std::fmt;

pub fn timed_print(args: fmt::Arguments) {
    let now = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap()
        .as_secs();
    println!("[{}] {}", now, args);
}

#[macro_export]
macro_rules! tprint {
    ($($arg:tt)*) => {
        $crate::utils::timed_print(format_args!($($arg)*))
    };
}

pub fn init_logger() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp(None)
        .init();
}