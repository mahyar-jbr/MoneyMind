import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="grid min-h-svh place-items-center px-6">
      <SignUp />
    </div>
  );
}
