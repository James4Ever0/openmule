use std::time::SystemTime;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;

pub fn timed_print(message: &str) {
    let now = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap()
        .as_secs();
    println!("[{}] {}", now, message);
}

pub async fn pipe(
    mut source: TcpStream,
    mut destination: TcpStream,
    label: &str,
) -> tokio::io::Result<()> {
    timed_print(&format!("Running pipe thread: {}", label));
    let (mut source_reader, mut source_writer) = source.split();
    let (mut dest_reader, mut dest_writer) = destination.split();

    let read_task = async move {
        let mut buf = [0; 4096];
        loop {
            timed_print(&format!("Receiving data at pipe thread {}", label));
            let n = match source_reader.read(&mut buf).await {
                Ok(n) if n == 0 => break,
                Ok(n) => n,
                Err(e) => {
                    timed_print(&format!("Pipe thread {} read error: {}", label, e));
                    break;
                }
            };
            timed_print(&format!(
                "Received {} bytes at pipe thread {}: {:x?}",
                n,
                label,
                &buf[..n.min(10)]
            ));
            timed_print(&format!("Sending data at pipe thread {}", label));
            if let Err(e) = dest_writer.write_all(&buf[..n]).await {
                timed_print(&format!("Pipe thread {} write error: {}", label, e));
                break;
            }
        }
        let _ = dest_writer.shutdown().await;
        Ok::<(), tokio::io::Error>(())
    };

    let write_task = async move {
        let mut buf = [0; 4096];
        loop {
            let n = match dest_reader.read(&mut buf).await {
                Ok(n) if n == 0 => break,
                Ok(n) => n,
                Err(e) => {
                    timed_print(&format!("Pipe thread {} read error: {}", label, e));
                    break;
                }
            };
            if let Err(e) = source_writer.write_all(&buf[..n]).await {
                timed_print(&format!("Pipe thread {} write error: {}", label, e));
                break;
            }
        }
        let _ = source_writer.shutdown().await;
        Ok::<(), tokio::io::Error>(())
    };

    tokio::select! {
        _ = read_task => {},
        _ = write_task => {},
    }

    timed_print(&format!("Pipe thread {} finished", label));
    Ok(())
}
